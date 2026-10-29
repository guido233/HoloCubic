#!/usr/bin/env python3
"""Generate the native RevB display schematic from the reviewed manifest."""
import argparse, copy, json, math, uuid
from pathlib import Path
from revise_schematic import Q,get,alln,prop,write,num,effects,field,line,pin_node,symbol_definition,globalize_labels

POSITIONS={'CON1':(64.77,67.31),'C1':(64.77,125.73),'C2':(64.77,146.05),
           'LCD1':(205.74,87.63),'U1':(344.17,72.39),'R2':(344.17,105.41),
           'Q1':(344.17,133.35),'R1':(302.26,158.75),'R3':(377.19,158.75),
           'C3':(318.77,190.5),'C4':(377.19,190.5)}
PIN_METADATA={
'LCD1': [('1','GND','power_in'),('2','LED_K','passive'),('3','LED_A','power_in'),('4','VDD','power_in'),('5','GND','power_in'),('6','GND','power_in'),('7','DC','input'),('8','~{CS}','input'),('9','SCL','input'),('10','SDA','input'),('11','~{RESET}','input'),('12','GND','power_in')],
'Q1':[('1','G','input'),('2','S','passive'),('3','D','open_collector')],
# EN is the internally biased analog shunt node in the manufacturer's
# two-transistor circuit (AL5802 datasheet Fig. 16), not a floating logic input.
'U1':[('1','OUT','open_collector'),('2','BIAS','power_in'),('3','EN/SHUNT','passive'),('4','GND','power_in'),('5','FB','input'),('6','REXT','passive')],
}

def rebuild(manifest_path,output):
    m=json.loads(Path(manifest_path).read_text());root=m['root_uuid'];ns=uuid.UUID(root)
    stable=lambda s:Q(str(uuid.uuid5(ns,s)))
    def text(txt,x,y,size=1):return ['text',Q(txt),['at',num(x),num(y),'0'],effects(size,'left bottom'),['uuid',stable('text:'+txt)]]
    doc=['kicad_sch',['version','20260306'],['generator','eeschema'],['generator_version',Q('10.0')],['uuid',Q(root)],['paper',Q('A3')],
         ['title_block',['title',Q('HoloCubic Naive RevB — Display board')],['date',Q('2026-10-29')],['rev',Q('B')],['company',Q('HoloCubic / original design: peng-zhihui')],['comment','1',Q('P133H002 bare ST7789V panel / 24mA nominal constant-current backlight')],['comment','2',Q('Engineering revision; panel/FFC fit, power-up and current measurements pending.')]]]
    libs={};specs={};parts=m['parts'];meta={}
    for p in parts:
        ref=p['ref'];pins={no:{'name':name,'type':typ,'net':p['pins'][no]} for no,name,typ in PIN_METADATA[ref]} if ref in PIN_METADATA else {no:{'name':'SHIELD' if no=='MP' else no,'type':'passive','net':net} for no,net in p['pins'].items()}
        # Q1 is an insulated-gate NMOS. Use a labelled G/S/D box rather than
        # the main-board helper's bipolar-transistor glyph for key Q1.
        meta[ref]=pins;key='Q_NMOS' if ref=='Q1' else (ref[0] if ref[0] in ['R','C'] and ref[1:].isdigit() else ref)
        if key not in libs:libs[key],pts,h=symbol_definition(key,pins);specs[key]=(pts,h)
    doc.append(['lib_symbols',*[copy.deepcopy(l) for l in libs.values()]])
    for p in parts:
        ref=p['ref'];pins=meta[ref];x,y=POSITIONS[ref];key='Q_NMOS' if ref=='Q1' else (ref[0] if ref[0] in ['R','C'] and ref[1:].isdigit() else ref);pts,h=specs[key]
        sym=['symbol',['lib_id',Q('HoloCubicExt:'+key)],['at',num(x),num(y),'0'],['unit','1'],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',Q(p.get('uuid',str(stable('symbol:'+ref))))],field('Reference',ref,x,y-h/2-5.08,1.27),field('Value',p['value'],x,y-h/2-2.54),field('Footprint',p['footprint'],x,y,1,True),field('Datasheet','',x,y,1,True),field('MPN',p['mpn'],x,y,1,True),field('DesignNote',p['note'],x,y,1,True)]
        for no in pins:sym.append(['pin',Q(no),['uuid',stable('pin:'+ref+':'+no)]])
        sym.append(['instances',['project',Q('ExtendBoard'),['path',Q('/'+root),['reference',Q(ref)],['unit','1']]]]);doc.append(sym)
        for no,pin in pins.items():
            px,py,a=pts[no];px+=x;py=y-py;net=pin['net']
            if net is None:doc.append(['no_connect',['at',num(px),num(py)],['uuid',stable('nc:'+ref+':'+no)]]);continue
            ex=px+(-7.62 if a==0 else 7.62)
            doc += [['wire',['pts',['xy',num(px),num(py)],['xy',num(ex),num(py)]],['stroke',['width','0'],['type','default']],['uuid',stable('wire:'+ref+':'+no)]],['label',Q(net),['at',num(ex),num(py),'0'],effects(1,'left bottom' if a==180 else 'right bottom'),['uuid',stable('label:'+ref+':'+no)]]]
    for x1,y1,x2,y2,title in [(10,20,130,245,'1  Eight-way FFC / panel logic power'),(140,20,270,245,'2  1.3 inch 240 x 240 TFT panel'),(280,20,410,245,'3  Current-controlled backlight / active-low PWM')]:
        doc += [['polyline',['pts',['xy',num(x1),num(y1)],['xy',num(x2),num(y1)],['xy',num(x2),num(y2)],['xy',num(x1),num(y2)],['xy',num(x1),num(y1)]],['stroke',['width','0.254'],['type','default']],['fill',['type','none']],['uuid',stable('frame:'+title)]],text(title,x1+2.54,y1+6.35,1.5)]
    notes=[('Hirose FH12-8S-0.5SH(55), 0.5 mm pitch.\nFFC must reverse pin numbering between boards.\nDisplay pin 1 mates with main-board pin 8.\nMounting pads MP are grounded.',14,231),
           ('Panel FPC: 12 contacts, 0.7 mm pitch.\nST7789V CS is permanently low; write-only SPI.\nPanel logic is 3.3V. Backlight anode is switched 5V.\nPin 2 LED_K goes to AL5802; never tie it to GND.\nBare-panel FPC/outline must be checked against the\nselected P133H002 manufacturer drawing.',144,231),
           ('GPIO5 / LCD_BL low: Q1 off, AL5802 enabled.\nGPIO5 high: Q1 on, EN low, backlight off.\nAL5802 nominal I = 0.65V / 27 ohm = 24.1mA.\nRequire BIAS >= 4.5V and OUT >= 0.8V.\nMeasure LED current, sink voltage and temperature.\nBrief current-limited flash is possible before 3.3V rises.',284,237)]
    for t,x,y in notes:doc.append(text(t,x,y))
    flag=['symbol',Q('PWR_FLAG'),['power'],['pin_names',['offset','0']],['exclude_from_sim','no'],['in_bom','no'],['on_board','no'],field('Reference','#FLG',0,4,1,True),field('Value','PWR_FLAG',0,3),['symbol',Q('PWR_FLAG_0_1'),line([(0,0),(0,1.27),(-1.27,2.54),(0,3.81),(1.27,2.54),(0,1.27)])],['symbol',Q('PWR_FLAG_1_1'),pin_node('1','pwr','power_out',0,0,90,0,False)]]
    get(doc,'lib_symbols').append(copy.deepcopy(flag));libs['PWR_FLAG']=flag
    for i,net in enumerate(['3V3','VDD_5V','GND']):
        x=35.56+30.48*i;y=185.42
        doc += [['symbol',['lib_id',Q('HoloCubicExt:PWR_FLAG')],['at',num(x),num(y),'0'],['unit','1'],['in_bom','no'],['on_board','no'],['dnp','no'],['uuid',stable('flag:'+net)],field('Reference','#FLG%03d'%(i+1),x,y-5,1,True),field('Value','PWR_FLAG',x,y-5),['pin',Q('1'),['uuid',stable('flagpin:'+net)]],['instances',['project',Q('ExtendBoard'),['path',Q('/'+root),['reference',Q('#FLG%03d'%(i+1))],['unit','1']]]]],['label',Q(net),['at',num(x),num(y),'0'],effects(1,'left bottom'),['uuid',stable('flaglabel:'+net)]]]
    for l in alln(get(doc,'lib_symbols'),'symbol'):l[1]=Q('HoloCubicExt:'+str(l[1]))
    globalize_labels(doc)
    write(output,doc);outdir=Path(output).parent
    write(outdir/'HoloCubicExt.kicad_sym',['kicad_symbol_lib',['version','20241209'],['generator','kicad_symbol_editor'],*[copy.deepcopy(l) for l in libs.values()]])
    write(outdir/'sym-lib-table',['sym_lib_table',['version','7'],['lib',['name',Q('HoloCubicExt')],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/HoloCubicExt.kicad_sym')],['options',Q('')],['descr',Q('Local RevB display-board symbols')]]])
    paths={p['ref']:'/'+root+'/'+p.get('uuid',str(stable('symbol:'+p['ref']))) for p in parts}
    print(json.dumps({'parts':len(parts),'paths':paths},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args();rebuild(a.manifest,a.output)
