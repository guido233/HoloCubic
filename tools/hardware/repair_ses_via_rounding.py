#!/usr/bin/env python3
"""Snap only reported, unlocked trace endpoints within 2um of a via centre.

Specctra integer-micrometre rounding can leave a half-micrometre mismatch.
This narrow repair never moves a via or locked copper and does not suppress
checks. It requires a fresh native DRC report and a new output path, followed
by another native DRC run before adoption.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from revise_schematic import alln, get, parse, write

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input',type=Path);ap.add_argument('report',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args()
    if args.output.exists() or args.output.resolve()==args.input.resolve():
        raise ValueError('Use a new output file')
    raw=args.input.read_bytes();tree=parse(raw.decode());changes=[]
    tracks={str(get(t,'uuid')[1]):t for t in alln(tree,'segment')}
    vias={str(get(v,'uuid')[1]):v for v in alln(tree,'via')}
    for item in json.loads(args.report.read_text())['violations']:
        if item['type']!='track_not_centered_on_via':continue
        ids=[str(n['uuid'])for n in item['items']]
        trace_ids=[uid for uid in ids if uid in tracks];via_ids=[uid for uid in ids if uid in vias]
        if len(trace_ids)!=1 or len(via_ids)!=1:raise ValueError('Ambiguous reported contact')
        track=tracks[trace_ids[0]];via=vias[via_ids[0]]
        if get(track,'locked') and get(track,'locked')[1]=='yes':raise ValueError('Refusing to change locked copper')
        if get(track,'net')[-1]!=get(via,'net')[-1]:raise ValueError('Contact nets differ')
        at=get(via,'at')[1:3]
        endpoint=min((get(track,key)for key in ['start','end']),
                     key=lambda p:math.dist(list(map(float,p[1:3])),list(map(float,at))))
        distance=math.dist(list(map(float,endpoint[1:3])),list(map(float,at)))
        if not 0<distance<=.002:raise ValueError('Mismatch exceeds the limited rounding repair')
        changes.append({'trace':trace_ids[0],'via':via_ids[0],'endpoint':endpoint[0],
                        'before_mm':endpoint[1:3].copy(),'after_mm':at.copy(),'distance_mm':distance})
        endpoint[1:3]=at
    write(args.output,tree)
    if args.input.read_bytes()!=raw:raise RuntimeError('Input changed')
    args.output.with_suffix('.rounding.json').write_text(json.dumps({
        'input_sha256':hashlib.sha256(raw).hexdigest(),
        'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'requires_native_recheck':True,'changes':changes},indent=2)+'\n')
    print('Adjusted',len(changes),'reported endpoint contacts; native recheck required')

if __name__=='__main__':main()
