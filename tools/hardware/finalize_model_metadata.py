#!/usr/bin/env python3
"""Add explicitly labelled body envelopes and correct D2's maximum-body court.

Writes a new board only. Pads, poses, all copper, zones and rules must remain
byte-equivalent as parsed structures. Run native DRC before adopting the copy,
then export its matching local footprint library. The model boxes are visual
package limits, not manufacturer CAD or an assembly-fit certificate.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import uuid

from revise_schematic import Q, alln, get, parse, prop, write

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_ASSETS=ROOT/'1.Hardware/RevB-KiCad/Naive/MainBoard/3dmodels/max_body_bounding_envelopes.json'
DEFAULT_COURT=Path(__file__).with_name('data')/'d2_max_courtyard.json'

def protected(board):
    copper=[n for n in board if isinstance(n,list) and n and n[0] in ['segment','via','arc','zone']]
    footprints={str(prop(f,'Reference')[2]):{
        'pose':get(f,'at'),'layer':get(f,'layer'),'pads':alln(f,'pad'),
        'path':get(f,'path'),'id':f[1]}
        for f in alln(board,'footprint')}
    return copy.deepcopy((copper,footprints,get(board,'setup'),get(board,'layers')))

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--assets',type=Path,default=DEFAULT_ASSETS)
    ap.add_argument('--courtyard',type=Path,default=DEFAULT_COURT)
    args=ap.parse_args()
    if args.output.exists() or args.output.resolve()==args.input.resolve():
        raise ValueError('Use a new output path; the input must remain unchanged')
    initial_hash=digest(args.input);board=parse(args.input.read_text());before=protected(board)
    fps={str(prop(f,'Reference')[2]):f for f in alln(board,'footprint')}
    assets=json.loads(args.assets.read_text());changed=[]
    for item in assets['assets']:
        path=args.assets.parent/item['filename']
        if not path.is_file() or digest(path)!=item['sha256']:
            raise ValueError('Missing or changed verified envelope: '+path.name)
        for ref in item['references']:
            fp=fps[ref]
            for model in alln(fp,'model'):fp.remove(model)
            fp.append(['model',Q('${KIPRJMOD}/3dmodels/'+item['filename']),
                ['offset',['xyz','0','0','0']],['scale',['xyz','1','1','1']],
                ['rotate',['xyz','0','0','0']]])
            changed.append(ref)
    data=json.loads(args.courtyard.read_text());fp=fps['D2']
    for kind in ['fp_line','fp_arc','fp_rect','fp_poly']:
        for shape in alln(fp,kind):
            if get(shape,'layer',['layer',''])[1]=='F.CrtYd':fp.remove(shape)
    points=data['polygon_local_xy_mm']
    if points[0]==points[-1]:points=points[:-1]
    for i,(a,z) in enumerate(zip(points,points[1:]+points[:1])):
        fp.append(['fp_line',['start',*[f'{float(v):.6f}'for v in a]],
            ['end',*[f'{float(v):.6f}'for v in z]],
            ['stroke',['width','0.05'],['type','default']],['layer',Q('F.CrtYd')],
            ['uuid',Q(str(uuid.uuid5(uuid.NAMESPACE_URL,'holocubic-revb-d2-max-courtyard-'+str(i))))]])
    if before!=protected(board):raise RuntimeError('Protected electrical or board geometry changed')
    write(args.output,board)
    if before!=protected(parse(args.output.read_text())):raise RuntimeError('Serialization changed protected geometry')
    if digest(args.input)!=initial_hash:raise RuntimeError('Input changed')
    report={'classification':'Metadata/courtyard copy; requires native DRC before adoption',
        'input_sha256':initial_hash,'output_sha256':digest(args.output),
        'asset_manifest_sha256':digest(args.assets),'courtyard_spec_sha256':digest(args.courtyard),
        'envelope_references':changed,'D2_max_body_mm':data['max_body_mm'],
        'D2_courtyard_margin_mm':data['offset_mm'],
        'copper_pads_poses_zones_rules_unchanged':True,
        'models_are_exact_manufacturer_CAD':False}
    args.output.with_suffix('.models.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
