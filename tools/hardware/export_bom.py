#!/usr/bin/env python3
"""Export the 69 actual schematic instances to a traceable procurement dataset.

Reads fresh native KiCad XML netlists. Does not write either PCB or schematic.
The JSON is the input to the formatted purchasing workbook; quantity is per unit.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import date
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '1.Hardware/RevB-KiCad/Naive'
from verify_hardware import DEFAULT_CLI, pcb_circuit
from revise_schematic import get
CLI = DEFAULT_CLI

EXACT = {
    'CA-C03': ('CrossAir / 广州寒武纪', '厂家资料已核', '工程焊盘偏离厂家推荐尺寸；pin2固定端NC；需焊接、VNA及整壳RF验收', 'https://www.gzhwjdz.com/DownLoad/45858.html'),
    '104031-0811': ('Molex', 'Active（原厂）', 'RevB2焊盘；检测9/10均GND未用；需插卡及保卡实测', 'https://www.molex.com/en-us/products/part-detail/1040310811'),
    'USB4105-GF-A': ('GCT', '厂家图纸已核', '按GF-A后缀和B4图采购；需USB数据、热插拔及壳口样件验收', 'https://gct.co/connector/usb4105'),
    'FH12-8S-0.5SH(55)': ('Hirose', '厂家图纸已核', '8P / 0.5mm / 0.3mm厚FFC，bottom contact；排线接触面及长度另行锁定', 'https://www.hirose.com/product/p/CL0586-0744-5-55'),
    'CP2102-GMR': ('Silicon Labs', '预计完整生产至少至2029-03', '经典CP2102 QFN28；核优选修订与可追溯批次，不以CP2102N替代', 'https://www.silabs.com/interface/usb-bridges/classic/device.cp2102'),
    'MPU-6050': ('TDK InvenSense', 'Obsolete（原厂）', '仅可追溯旧库存复刻；需来料功能检验；非持续量产供货方案', 'https://product.tdk.com/en/search/sensor/mortion-inertial/imu/info?part_no=MPU-6050'),
    'ESP32-PICO-D4': ('Espressif', 'NRND（原厂）', 'PICO系列v1.5均NRND；保持D4，替代需重新设计；EP/paste/via按RevB受控封装', 'https://documentation.espressif.com/esp32-pico_series_datasheet_en.html'),
    'BH1750FVI-TR': ('ROHM', 'NRND（渠道，待原厂确认）', 'WSOF6I；向原厂/授权渠道确认供货与追溯，不以模块代替裸IC', 'https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6165/bh1750fvi-e.pdf'),
    'WS2812B-V5/W': ('Worldsemi', '厂家资料已核', '完整V5/W版本；1VDD/2DOUT/3GND/4DIN；5V供电及AHCT缓冲', 'https://datasheet.lcsc.com/lcsc/2206131216_Worldsemi-WS2812B-V5-W_C2874885.pdf'),
    'P133H002': ('POLCD', '电气候选，机械待验收', '裸屏12pin/0.7mm/ST7789V；尾排绕板、焊盘注册及整壳装配须样件确认', 'https://www.polcd-digital.com/products/1-3-inch-tft-lcd-display-240x240-pixels-p133h002'),
    'AO3400A': ('Alpha & Omega Semiconductor', '未单独核验生命周期', 'G1/S2/D3逻辑NMOS；不可用NPN替代，以免加载GPIO5启动strap', 'https://www.aosmd.com/sites/default/files/res/datasheets/AO3400A.pdf'),
    'AL5802-7': ('Diodes Incorporated', '未单独核验生命周期', 'SOT26恒流驱动；27ohm设约24mA典型值，须测实物背光电流', 'https://www.diodes.com/assets/Datasheets/AL5802.pdf'),
    'MMBT3904-7-F': ('Diodes Incorporated', '厂家图纸已核', 'B1/E2/C3；按Diodes受控SOT23焊盘，不任意替换不同引脚8050', 'https://www.diodes.com/assets/Datasheets/MMBT3904.pdf'),
    'VLS3012HBX-2R2M-N': ('TDK', '未单独核验生命周期', '2.2uH；完整HBX/-N订货号，电感饱和及温升按供电实测验收', ''),
}

TI = {'TPS62162DSGR':'TPS62162','TPS22918DBVR':'TPS22918',
      'TPD4E05U06DQAR':'TPD4E05U06','SN74AHCT1G125DCKR':'SN74AHCT1G125',
      'TPD1E10B06DPYR':'TPD1E10B06'}

def procurement(mpn):
    if mpn in EXACT:return EXACT[mpn]
    if mpn in TI:return ('Texas Instruments','Active（原厂）','保持完整封装后缀与引脚定义','https://www.ti.com/product/'+TI[mpn])
    if mpn.startswith('RC'):
        return ('YAGEO','未单独核验生命周期','', 'https://www.yageogroup.com/component-documentation/download/specsheet/'+mpn)
    if mpn.startswith('GRM'):
        return ('Murata','原理图已选完整MPN','MLCC标称值不代表工作偏压下有效值',
                'https://ds.murata.com/simserve/characteristics?ReqType=TechPDF&partnumber='+mpn[:-1]+'&techpdfname=technical_pdf_Capacitor01&lang=en')
    raise ValueError('No manufacturer identity for '+mpn)

def natural(ref):return tuple(int(x)if x.isdigit()else x for x in re.split('(\d+)',ref))

def export(cli, output):
    parts=[];sources=[];pcbs=[]
    with tempfile.TemporaryDirectory(prefix='holocubic-bom-') as temp:
        for board,wanted in [('MainBoard',58),('ExtendBoard',11)]:
            sch=BASE/board/(board+'.kicad_sch');xml=Path(temp)/(board+'.xml')
            subprocess.run([str(cli),'sch','export','netlist','--format','kicadxml','--output',str(xml),str(sch)],check=True,capture_output=True,
                           env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            sources.append({'schematic':str(sch.relative_to(ROOT)),'sha256':hashlib.sha256(sch.read_bytes()).hexdigest()})
            pcb=BASE/board/(board+'.kicad_pcb')
            pcbs.append({'pcb':str(pcb.relative_to(ROOT)),'sha256':hashlib.sha256(pcb.read_bytes()).hexdigest()})
            rows=[]
            _,_,footprints=pcb_circuit(BASE/board/(board+'.kicad_pcb'))
            for c in ET.parse(xml).getroot().find('components'):
                ref=c.attrib['ref']
                if ref.startswith('#'):continue
                fields={f.attrib['name']:f.text or '' for f in c.find('fields')}
                mpn=fields.get('MPN','').strip()
                if not mpn:raise ValueError('Missing MPN: '+board+'.'+ref)
                manufacturer,status,note,source=procurement(mpn)
                if board=='MainBoard':
                    if ref=='C20':note='4.7uF/10V/X5R0402；5V典型约1.88uF、5.5V约1.7uF；非保证下限，量产须采样'
                    elif ref=='C7':note='1uF/16V0402；3V3典型有效约0.55uF，EN实际复位时序须测'
                    elif ref=='C15':note='入口1uF/16V0402；5V典型有效约0.35uF；热插拔时序须测'
                    elif ref=='C16':note='100pF/50V/C0G±5%0402；TI Eq3估算约0.425ms@5V，非最大值保证；CP_VDD到2.7V≤1ms、热插拔与入口电流须实测'
                    elif ref=='C3':note='22uF/25V0805；5V典型有效约10–11uF，非保证下限'
                    elif ref in ('C2','C4','C13'):note='22uF/25V0805；3V3典型有效约13–15uF，非保证下限'
                    elif ref=='R2':note='0ohm0402，型号额定1A；3V3A支路按ESP≤500mA设计分配'
                fp=footprints[ref];at=get(fp,'at');side=get(fp,'layer')[1]
                rows.append({'board':board,'reference':ref,'quantity':1,'value':c.findtext('value'),
                             'mpn':mpn,'manufacturer':manufacturer,'footprint':c.findtext('footprint'),
                             'side':side,'x_mm':float(at[1]),'y_mm':float(at[2]),
                             'rotation_deg':float(at[3]) if len(at)>3 else 0,
                             'supply_status':status,'acceptance_note':note,'source_url':source})
            if len(rows)!=wanted:raise ValueError('%s: expected %d real parts, got %d'%(board,wanted,len(rows)))
            parts.extend(sorted(rows,key=lambda p:natural(p['reference'])))
    result={'revision':'Naive RevB','date':date.today().isoformat(),'unit_quantity':1,'total_instances':len(parts),
            'unique_mpn_count':len({p['mpn']for p in parts}),'board_counts':{'MainBoard':58,'ExtendBoard':11},
            'scope':'69 PCB-mounted instances only. PCB fabrication, FFC, USB cable, SD card, optics/enclosure and tools are separate.',
            'placement_scope':'Native CAD coordinates, not a machine-specific pick-and-place file. LCD1 body is on B, tail solder pads on F; fold is unqualified.',
            'source_schematics':sources,'source_pcbs':pcbs,'parts':parts}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    # Text sidecars remain usable without a workbook runtime. Placement fields
    # are engineering coordinates, not a machine-specific pick-and-place job.
    with output.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(parts[0]));writer.writeheader();writer.writerows(parts)
    groups=defaultdict(list)
    for part in parts:groups[part['mpn']].append(part)
    with output.with_name(output.stem+'-grouped.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['MPN','Value','Quantity','Manufacturer','Board:Reference','Supply status','Acceptance notes','Source'])
        for mpn,rows in sorted(groups.items()):
            val=' / '.join(dict.fromkeys(p['value'] for p in rows))
            writer.writerow([mpn,val,len(rows),rows[0]['manufacturer'],
                             ', '.join(p['board']+':'+p['reference'] for p in rows),rows[0]['supply_status'],
                             '; '.join(dict.fromkeys(p['acceptance_note'] for p in rows if p['acceptance_note'])),rows[0]['source_url']])
    print('%d instances; %d exact MPNs; no missing fields -> %s'%(len(parts),result['unique_mpn_count'],output))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cli',type=Path,default=CLI);p.add_argument('--output',type=Path,default=BASE/'BOM.json');p.add_argument('--require-complete',action='store_true',help='All MPN fields are always required');a=p.parse_args();export(a.cli,a.output)
