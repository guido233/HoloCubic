#!/usr/bin/env python3
"""Check the RevB display's axial solder-landing allowance and draw a 1:1 guide.

Read-only source operation; standard library only. This does not qualify FPC
bending, lateral registration, supplier requirements or complete assembly.
The0.75mm minimum is a project manual-solder criterion, not a POLCD specification.
"""
from pathlib import Path
import argparse
import json
import hashlib
import itertools
import math
import html
from revise_schematic import parse,get,alln,prop
from mechanical_baseline import arc_points
ROOT=Path(__file__).resolve().parents[2]
SOURCE_PDF_SHA256='0656c42747e58621afb6cdcd8e28aba7539b7b49afb95bb5bc1533a01c7f5a3f'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board',type=Path,default=ROOT/'1.Hardware/RevB-KiCad/Naive/ExtendBoard/ExtendBoard.kicad_pcb')
    ap.add_argument('--schematic',type=Path)
    ap.add_argument('--output-dir',type=Path,required=True,help='A new or empty directory; existing artifacts are not overwritten')
    a=ap.parse_args();pcb=a.board.resolve();sch=(a.schematic or pcb.with_suffix('.kicad_sch')).resolve();D=a.output_dir.resolve()
    if D.exists() and any(D.iterdir()):ap.error('Use a new or empty output directory')
    D.mkdir(parents=True,exist_ok=True)
    r=parse(pcb.read_text());fps={prop(f,'Reference')[2]:f for f in alln(r,'footprint')};f=fps['LCD1'];at=get(f,'at');xc,yc=float(at[1]),float(at[2]);assert at[3]=='-90'
    pads=[]
    for p in alln(f,'pad'):
     a=get(p,'at');x,y=xc-float(a[2]),yc+float(a[1]);w,h=map(float,get(p,'size')[1:]);assert (w,h)==(.5,5.5)
     layers=list(get(p,'layers')[1:]);assert set(layers)=={'F.Cu','F.Mask'}
     pads.append({'pin':int(p[1]),'net':get(p,'net')[-1],'center_mm':[round(x,7),round(y,7)],'copper_bbox_mm':[round(x-h/2,7),round(y-w/2,7),round(x+h/2,7),round(y+w/2,7)],'mask_margin_mm':float(get(p,'solder_mask_margin')[1]),'paste_aperture':False})
    pads.sort(key=lambda p:p['pin']);xs=[p['copper_bbox_mm'][0]for p in pads];assert min(xs)==max(xs)==152.25
    assert [p['pin']for p in pads]==list(range(1,13)), 'Expected exactly12LCDcontacts'
    expected_nets=['GND','LED_K','VDD_5V','3V3','GND','GND','DC','GND','SCK','MOSI','RES','GND']
    for p,want_net in zip(pads,expected_nets):
        assert p['net']==want_net, 'LCDcontact functional pin mapping changed'
        assert p['mask_margin_mm']==.025, 'LCDmask margin differs from reviewed DFM choice'
        assert abs(p['center_mm'][0]-155)<1e-7 and abs(p['center_mm'][1]-(111.7736-.7*(p['pin']-1)))<1e-7, 'LCDpitch or nominal row datum changed'

    cases=[]
    for root,fold,length in itertools.product([163.0111,163.2111],[10.6,11.6],[1.8,2.2]):
     left=root-fold;right=left+length;overlap=max(0,min(157.75,right)-max(152.25,left));cases.append({'panel_tail_root_x_mm':root,'folded_root_to_contact_outer_edge_mm':fold,'exposed_contact_length_mm':length,'contact_interval_x_mm':[round(left,7),round(right,7)],'overlap_with_copper_mm':round(overlap,7),'passes_0p75mm_minimum':overlap>=.75})
    legacy=[]
    for center,length in itertools.product([155.71,156.71],[1.8,2.2]):
     left=center-length/2;right=center+length/2;overlap=max(0,min(157.75,right)-max(152.25,left));legacy.append({'assumed_center_x_mm':center,'contact_length_mm':length,'overlap_mm':round(overlap,7),'passes_0p75mm_minimum':overlap>=.75})
    result={'classification':'Axial solder landing allowance mathematically verified; overall FPC fit NOT qualified','source_pcb':'1.Hardware/RevB-KiCad/Naive/ExtendBoard/ExtendBoard.kicad_pcb','pcb_sha256':hashlib.sha256(pcb.read_bytes()).hexdigest(),'schematic_sha256':hashlib.sha256(sch.read_bytes()).hexdigest(),'datum':'Same nominal screen/PCB XY center(148.5011,105.0036); KiCad globalXY, unitsmm','manufacturer_source':'https://cdn.shopify.com/s/files/1/0657/1150/5511/files/P133H002.pdf?v=1779866387','manufacturer_pdf_sha256':SOURCE_PDF_SHA256,'drawing_page':9,'panel_BL_length_mm':[29.22,.2],'folded_outer_edge_dimension_mm':[11.10,.5],'contact_length_mm':[2.0,.2],'contact_length_tolerance_basis':'Page9 NOTE9 unmarked tolerance +/-0.2mm. This is conservative against assuming exactly2.0mm. Supplier-approved final drawing still required.','panel_tail_root_x_interval_mm':[163.0111,163.2111],'new_pad_copper_xy_mm':[5.5,.5],'pad_pitch_mm':.7,'nominal_adjacent_mask_web_mm':.15,'engineering_minimum_axial_overlap_mm':.75,'engineering_minimum_basis':'Chosen manual-solder assembly acceptance threshold, NOT a POLCD guaranteed requirement.','bare_fold_all_corner_cases':cases,'legacy_location_sensitivity_cases':legacy,'minimum_bare_fold_overlap_mm':min(c['overlap_with_copper_mm']for c in cases),'minimum_legacy_location_overlap_mm':min(c['overlap_mm']for c in legacy),'all_12_pads':pads,'check_count':12*(len(cases)+len(legacy)),'failed_count':0,'FPC_soldering_process':'Manual soldering after PCBA reflow, flux and controlled tinning, no solder-paste stencil aperture on longlands. Inspect all12contacts and bridges.','placements_mm_deg':{ref:[float(x)for x in get(f,'at')[1:]]for ref,f in fps.items()},'ground_plane_stitch_mm':[135,93,.6,.3],'legacy_complete_display_FPC_3d_model_removed':True,'limits':['No physical assembly or operation test performed.','Only the axial contact-overlap range is closed; bending to the contacts is not proved by this range.','No permitted FPC bend radius or allowable bending segment is supplied in the P133 drawing.','12pin lateral alignment and contact polarity/face must be confirmed; do not widen pads to hide pitch/registration uncertainty.','Screen adhesive thickness, component bump placement, full FPC envelope, closedcase assembly and cable actuation need supplier/sample evidence.','Changing pads adds soldering area but does not validate the unknown FPC route.']}
    assert all(c['passes_0p75mm_minimum']for c in cases+legacy)
    (D/'P133H002-interface-closure.json').write_text(json.dumps(result,indent=2)+'\n')
    # Physical1:1 guide with calibration bar; no invented routed FPC centerline.
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="148mm" height="105mm" viewBox="0 0 148 105">','<rect width="148" height="105" fill="white"/>','<style>text{font-family:Arial,sans-serif;fill:#17243b} .small{font-size:2.15px}.tiny{font-size:1.6px}</style>','<text x="8" y="8" font-size="3.5">P133H002 / Naive ExtendBoard - axial solder interface</text>','<text x="8" y="12" class="small">1:1 in mm. Print at 100%; verify calibration. No bend/case-fit qualification.</text>']
    # exact board paths, all native edges
    T=lambda x,y:(x-133.8072+10,y-91.8845+20)
    for n in r:
     if not isinstance(n,list)or not n or get(n,'layer',['',''])[1]!='Edge.Cuts':continue
     if n[0]=='gr_line': pts=[get(n,'start')[1:],get(n,'end')[1:]]
     elif n[0]=='gr_arc':pts=arc_points([float(x)for x in get(n,'start')[1:]],[float(x)for x in get(n,'mid')[1:]],[float(x)for x in get(n,'end')[1:]],step=.1)
     else:continue
     out=[T(float(a),float(b))for a,b in pts];svg.append('<polyline points="'+ ' '.join(f'{a:.6f},{b:.6f}'for a,b in out)+'" fill="none" stroke="#1f2937" stroke-width=".12"/>')
    for p in pads:
     x1,y1,x2,y2=p['copper_bbox_mm'];x,y=T(x1,y1);svg.append(f'<rect x="{x}" y="{y}" width="{x2-x1}" height="{y2-y1}" rx=".05" fill="#bf7f26"/>')
     xx,yy=T(x2+.4,p['center_mm'][1]+.2);svg.append(f'<text x="{xx}" y="{yy}" font-size=".85">{p["pin"]}</text>')
    for x,col in [(153.0111,'#2563eb'),(156.21,'#bd2835')]:
     a,b=T(x,103.3);c,d=T(x,112.6);svg.append(f'<path d="M{a},{b} L{c},{d}" stroke="{col}" stroke-width=".1" stroke-dasharray=".5 .35"/>')
    for ref in ['CON1','Q1','R1','C1','R2','R3']:
     a=get(fps[ref],'at');x,y=T(float(a[1]),float(a[2]));svg.append(f'<circle cx="{x}" cy="{y}" r=".22" fill="#446"/><text x="{x+.4}" y="{y+.2}" font-size="1.1">{ref}</text>')
    texts=[('Interface copper','5.5 x 0.50 mm, pitch 0.70 mm'),('Copper X interval','152.25 ... 157.75 mm'),('Pad1 / Pad12 Y','111.7736 / 104.0736 mm'),('Blue dashed line','bare folded drawing nominal contact center'),('Red dashed line','previous legacy nominal contact center'),('Worst axial overlap','0.9611 mm with +/-0.5, +/-0.2 and panel tolerance'),('Assembly process','manual FPC solder AFTER PCBA reflow'),('Stencil','NO F.Paste aperture on these12lands')]
    for i,(a,b)in enumerate(texts):
     y=22+i*4.4;svg.append(f'<text x="51" y="{y}" class="small">{html.escape(a)}: {html.escape(b)}</text>')
    svg+=['<path d="M10,60 L30,60 M10,58 L10,62 M30,58 L30,62" stroke="black" stroke-width=".2"/>','<text x="10" y="65" class="small">20.00 mm calibration</text>','<text x="8" y="73" class="small">UNRESOLVED: FPC permitted bend radius/segment, contact face, lateral registration,</text>','<text x="8" y="77" class="small">solder/adhesive thickness, enclosure datum and full cable path. No physical test performed.</text>','<text x="8" y="84" class="tiny">Datum: KiCadXY; nominal screen/PCB center(148.5011,105.0036). Dimensions are construction references.</text>',f'<text x="8" y="89" class="tiny">PCB SHA256: {result["pcb_sha256"]}</text>','<text x="8" y="94" class="tiny">Source: POLCD P133H002 RevA mechanical drawing page9, issued2021.10.7; full source hash in JSON.</text>','</svg>']
    (D/'P133H002-interface-guide-1to1.svg').write_text('\n'.join(svg)+'\n')
    print('report+SVG',result['pcb_sha256'],result['schematic_sha256'],result['minimum_bare_fold_overlap_mm'],result['check_count'])

if __name__=='__main__':main()
