#!/usr/bin/env python3
"""Route an isolated board copy, preserving locked copper and component poses.

Run with KiCad's Python and -B. Accepts official Freerouting JAR / Java 25+
or the fastroute executable, plus a KiCad CLI path. Does not edit the input board/project. A router's
own success is not acceptance: native KiCad DRC is always run on the result.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import pcbnew as k

def poses(board):
    return {f.GetReference():[f.GetPosition().x,f.GetPosition().y,
                             f.GetOrientationDegrees(),f.GetLayer()]
            for f in board.GetFootprints()}

def signature(t):
    points=sorted([(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)])
    return (type(t).__name__,t.GetNetname(),t.GetLayer(),
            t.GetWidth(k.F_Cu) if isinstance(t,k.PCB_VIA) else t.GetWidth(),
            tuple(points[0]),tuple(points[1]),t.GetDrillValue() if isinstance(t,k.PCB_VIA) else 0,
            (t.GetMid().x,t.GetMid().y) if isinstance(t,k.PCB_ARC) else None)

def sanitize_dsn(path):
    """Set new-route defaults; locked source copper is retained separately."""
    s=path.read_text()
    if '(unit um)' not in s: raise ValueError('DSN unit is not micrometres')
    # KiCad emits unlocked copper as "route". Specctra routers interpret
    # that as user-fixed, preventing rip-up of every imported trial route.
    # "normal" is movable; leave locked "fix" copper untouched.
    movable=s.count('(type route)')
    s=s.replace('(type route)','(type normal)')
    widths=[];clearances=[]
    def width(m):
        n=float(m[1]);widths.append(n);return '(width %g)'%max(150,n)
    def clearance(m):
        n=float(m[1]);clearances.append(n);return '(clearance %g'%max(127,n)
    s=re.sub(r'\(width ([\d.]+)\)',width,s)
    s=re.sub(r'\(clearance ([\d.]+)',clearance,s)
    # Preserve existing protected via definitions. Replacing their names could
    # produce duplicate padstacks or misrepresent original copper to the router.
    # Add a distinct new-route via when needed, including arbitrary layer names
    # such as imported Top1 / Bottom4 rather than assuming F.Cu / B.Cu.
    first_via=re.search(r'Via(\[\d+-\d+\])_[\d.]+:[\d.]+_um',s)
    if not first_via:raise ValueError('No exported through-via layer range')
    span=first_via[1];new='Via'+span+'_600:300_um'
    if '(padstack "'+new+'"' not in s:
        match=re.search(r'\(padstack "Via\[\d+-\d+\]_[\d.]+:[\d.]+_um"',s)
        if not match:raise ValueError('No exported through-via padstack')
        start=match.start();depth=0;quoted=False;escaped=False;end=None
        for i in range(start,len(s)):
            c=s[i]
            if quoted:
                if escaped:escaped=False
                elif c=='\\':escaped=True
                elif c=='"':quoted=False
            elif c=='"':quoted=True
            elif c=='(':depth+=1
            elif c==')':
                depth-=1
                if depth==0:end=i+1;break
        if end is None:raise ValueError('Malformed via padstack')
        block=s[start:end]
        block=re.sub(r'Via\[\d+-\d+\]_[\d.]+:[\d.]+_um',new,block)
        block=re.sub(r'(\(circle\s+[^()\s]+\s+)[\d.]+(\))',r'\g<1>600\2',block)
        s=s[:end]+'\n    '+block+s[end:]
    declaration=re.search(r'\(via\s+"Via\[\d+-\d+\]_[^)]*\)',s)
    if not declaration:raise ValueError('Missing structure via declaration')
    if new not in declaration[0]:
        s=s[:declaration.end()-1]+' "'+new+'"'+s[declaration.end()-1:]
    s=re.sub(r'\(use_via "[^"]+"\)','(use_via "'+new+'")',s)
    names=re.findall(r'\(padstack "([^"]+)"',s)
    if len(names)!=len(set(names)):raise ValueError('Duplicate DSN padstack definitions')
    path.write_text(s)
    return {'units':'um','min_new_route_width':150,'clearance':127,
            'unlocked_source_items_made_movable':movable,
            'new_through_via_diameter':600,'new_through_via_drill':300,
            'exported_rule_widths':widths,'exported_clearances':clearances}

def compact_main_classes(path):
    """Qualified dense signal vias and explicit plane/RF task separation.

    Ground copper and the protected RF arcs are checked in the final native
    board. Skipping their inaccurate Specctra tasks is never a DRC exclusion.
    """
    s=path.read_text()
    def end_at(start):
        depth=0;quoted=False;escaped=False
        for i in range(start,len(s)):
            c=s[i]
            if quoted:
                if escaped:escaped=False
                elif c=='\\':escaped=True
                elif c=='"':quoted=False
            elif c=='"':quoted=True
            elif c=='(':depth+=1
            elif c==')':
                depth-=1
                if not depth:return i+1
        raise ValueError('Malformed class/padstack')
    through=re.search(r'Via(\[\d+-\d+\])_600:300_um',s)
    if not through:raise ValueError('Missing power through-via')
    power='Via'+through[1]+'_600:300_um';small='Via'+through[1]+'_460:250_um'
    if '(padstack "'+small+'"' not in s:
        m=re.search(r'\(padstack "'+re.escape(power)+'"',s)
        if not m:raise ValueError('Expected declared power via')
        e=end_at(m.start());block=s[m.start():e].replace(power,small)
        block=re.sub(r'(\(circle\s+[^()\s]+\s+)600(\))',r'\g<1>460\2',block)
        s=s[:e]+'\n    '+block+s[e:]
    declaration=re.search(r'\(via\s+"Via\[\d+-\d+\]_[^)]*\)',s)
    if small not in declaration[0]:s=s[:declaration.end()-1]+' "'+small+'"'+s[declaration.end()-1:]
    # Source project has Default and Power classes. Preserve all net members,
    # giving GND and the already-protected antenna net their own task classes.
    for name in ['kicad_default','Power']:
        m=re.search(r'\(class '+name+r'\s',s)
        if not m:raise ValueError('Missing source net class '+name)
        e=end_at(m.start());block=s[m.start():e];cut=block.index('(circuit')
        head=block[:cut]
        for net in ['GND','NetA1_1']:head=re.sub(r'(?<!\S)'+net+r'(?!\S)','',head)
        block=head+block[cut:]
        if name=='Power':block=re.sub(r'\(width [\d.]+\)','(width 400)',block)
        else:block=block.replace('(use_via "'+power+'")','(use_via "'+small+'")')
        s=s[:m.start()]+block+s[e:]
    for name in ['Ground','RF']:
        match=re.search(r'\(class '+name+r'\s',s)
        if match:s=s[:match.start()]+s[end_at(match.start()):]
    m=re.search(r'\(class Power\s',s);e=end_at(m.start())
    extra='\n    (class Ground GND (circuit (use_via "'+small+'")) (rule (width 150) (clearance 127)))'
    extra+='\n    (class RF NetA1_1 (circuit (use_via "'+small+'")) (rule (width 200) (clearance 127)))'
    s=s[:e]+extra+s[e:]
    path.write_text(s)
    return {'signal_via_um':[460,250],'minimum_annulus_um':105,
            'power_route_width_um':400,'protected_main_power_width_unchanged':True,
            'ground_and_rf_validated_by_native_drc':True}

def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--board',type=Path,required=True)
    p.add_argument('--project-dir',type=Path,required=True)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--backend',choices=['freerouting','fastroute'],default='freerouting')
    p.add_argument('--java',type=Path)
    p.add_argument('--jar',type=Path)
    p.add_argument('--fastroute',type=Path)
    p.add_argument('--max-time',type=int,default=180)
    p.add_argument('--initial-session',type=Path)
    p.add_argument('--cli',type=Path,required=True)
    p.add_argument('--passes',type=int,default=25)
    p.add_argument('--ground-plane',choices=['none','bottom'],default='none')
    p.add_argument('--keep-plane-layer',action='append',default=[],help='Retain a native plane on this named layer in the router input')
    p.add_argument('--power-layer',action='append',default=[],help='Declare a retained GND plane as DSN power; prohibit foreign tracks on it')
    p.add_argument('--skip-fanout',action='store_true')
    p.add_argument('--keep-existing',action='store_true')
    p.add_argument('--compact-main',action='store_true')
    p.add_argument('--plane-ground',action='store_true',help='Skip router ground tasks; native DRC must still prove every ground connection')
    p.add_argument('--skip-router-power',action='store_true',help='Preserve completed source power wiring/planes; native DRC still checks all power connections')
    p.add_argument('--neck-width-um',type=float)
    a=p.parse_args();source=a.board.resolve();project=a.project_dir.resolve();out=a.workdir.resolve()
    if a.backend=='freerouting' and (a.java is None or a.jar is None):p.error('Freerouting requires --java and --jar')
    if a.backend=='fastroute' and a.fastroute is None:p.error('fastroute requires --fastroute')
    if out==project or project in out.parents: p.error('Workdir must be outside the source project')
    if out.exists() and any(out.iterdir()): p.error('Use a fresh empty workdir')
    out.mkdir(parents=True,exist_ok=True)
    # Use the real project basename so native schematic parity works on the copy.
    paired=[f for f in project.glob('*.kicad_pro') if f.with_suffix('.kicad_sch').is_file()]
    matching=[f for f in paired if f.stem==source.stem]
    if len(matching)==1:project_file=matching[0]
    elif len(paired)==1:project_file=paired[0]
    else:raise ValueError('Select an unambiguous project with a matching schematic')
    stem=project_file.stem
    project_rules=json.loads(project_file.read_text()).get('board',{}).get('design_settings',{}).get('rules',{})
    edge_um=1000*float(project_rules.get('min_copper_edge_clearance',.25))
    for f in project.iterdir():
        if f.suffix in ['.kicad_pro','.kicad_sch','.kicad_sym','.kicad_dru'] or f.name in ['fp-lib-table','sym-lib-table']:
            shutil.copy2(f,out/f.name)
        elif f.is_dir() and f.suffix=='.pretty':shutil.copytree(f,out/f.name)
    pcb=out/(stem+'.kicad_pcb');shutil.copy2(source,pcb)
    original=k.LoadBoard(str(pcb));before=poses(original)
    locked=Counter(signature(t) for t in original.GetTracks() if t.IsLocked())
    route_board=k.LoadBoard(str(pcb));removed=[]
    for z in list(route_board.Zones()):
        if z.GetIsRuleArea():
            # Specctra exports these as full wire obstacles even when KiCad
            # restricts only copper fill/pad placement. Components never move;
            # the output retains every original native rule area for DRC.
            if not z.GetDoNotAllowTracks() and not z.GetDoNotAllowVias():
                removed.append(z);route_board.Remove(z)
        elif not ((a.ground_plane=='bottom' and z.GetNetname()=='GND' and z.GetLayer()==k.B_Cu) or
                  route_board.GetLayerName(z.GetLayer()) in a.keep_plane_layer):
            removed.append(z);route_board.Remove(z)
    if not a.keep_existing:
        for t in list(route_board.GetTracks()):
            if not t.IsLocked():removed.append(t);route_board.Remove(t)
    dsn=out/(stem+'.dsn');ses=out/(stem+'.ses')
    if not k.ExportSpecctraDSN(route_board,str(dsn)):raise RuntimeError('DSN export failed')
    shutil.copy2(dsn,out/(stem+'-exported.dsn'))
    rules=sanitize_dsn(dsn)
    if a.compact_main:rules['compact_main']=compact_main_classes(dsn)
    if a.power_layer:
        content=dsn.read_text()
        for name in a.power_layer:
            if name not in a.keep_plane_layer:p.error('--power-layer requires the same --keep-plane-layer')
            plane_nets={z.GetNetname() for z in route_board.Zones() if not z.GetIsRuleArea() and route_board.GetLayerName(z.GetLayer())==name}
            if plane_nets!={'GND'}:raise ValueError('Dedicated plane must contain only GND: '+name)
            pattern=r'(\(layer '+re.escape(name)+r'\s+\(type )signal(\))'
            content,count=re.subn(pattern,r'\g<1>power\2',content)
            if count!=1:raise ValueError('Cannot declare one DSN power layer: '+name)
        dsn.write_text(content);rules['signal_tracks_excluded_from_plane_layers']=a.power_layer
    if a.backend=='fastroute':
        command=[str(a.fastroute),'-de',str(dsn),'-do',str(ses),
                 '--max-time='+str(a.max_time),'--report='+str(out/'router-report.json'),
                 '--diagnose','--multi-start=2','--router.autorouter.max_threads=2',
                 '--router.optimizer.max_threads=2','--router.autorouter.max_passes='+str(a.passes),
                 '--router.autorouter.min_passes='+str(min(30,a.passes)),
                 '--no-neckdown-classes=Power','--router.min_trace_width_um=104',
                 '--router.copper_to_edge_clearance_um='+str(edge_um),
                 '--router.neck_width_um='+str(max(104,a.neck_width_um or 104))]
        if a.compact_main:
            ignored=['RF']+(['Ground'] if a.plane_ground else [])+(['Power'] if a.skip_router_power else [])
            command.append('--router.autorouter.ignore_net_classes='+','.join(ignored))
        if a.initial_session:command.append('--initial-session='+str(a.initial_session.resolve()))
    else:command=[str(a.java),'-Xmx8g','-Djava.awt.headless=true','-jar',str(a.jar),
             '-de',str(dsn),'-do',str(ses),'--router.autorouter.max_passes='+str(a.passes),
             '-mt','2','-da','--gui.enabled=false','--api_server.enabled=false',
             '--router.optimizer.max_threads=2',
             '--user_data_path='+str(out/'router-data')]
    if a.skip_fanout:command.append('--router.fanout.enabled=false')
    if a.compact_main and a.backend=='freerouting':command.append('--router.autorouter.ignore_net_classes=Ground,RF')
    if a.neck_width_um is not None and a.backend=='freerouting':
        if a.neck_width_um<101.6:p.error('Neck width must satisfy the qualified 101.6um minimum')
        command+=['--router.neck_width_um='+str(a.neck_width_um),'--router.automatic_neckdown=false']
    with (out/'router.log').open('w') as log:
        result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=max(1200,a.max_time+120))
    if result.returncode or not ses.exists():raise RuntimeError('Routing failed; see '+str(out/'router.log'))
    if not k.ImportSpecctraSES(original,str(ses)):raise RuntimeError('SES import failed')
    # DSN uses 0.1um coordinates. Restore harmless sub-grid rounding exactly;
    # reject any meaningful component movement before accepting routed copper.
    quantization=[]
    for f in original.GetFootprints():
        ref=f.GetReference();wanted=before[ref];actual=poses(original)[ref]
        dx=actual[0]-wanted[0];dy=actual[1]-wanted[1]
        if actual[3]!=wanted[3] or abs(actual[2]-wanted[2])>1e-6 or abs(dx)>100 or abs(dy)>100:
            raise RuntimeError('Router moved component '+ref)
        if dx or dy:
            quantization.append({'ref':ref,'x_nm':dx,'y_nm':dy})
            f.SetPosition(k.VECTOR2I(wanted[0],wanted[1]))
    same_poses=before==poses(original)
    after=Counter(signature(t) for t in original.GetTracks())
    missing=list((locked-after).elements())
    if not same_poses or missing:raise RuntimeError('Router moved components or altered protected copper')
    for t in original.GetTracks():
        if not isinstance(t,k.PCB_VIA) and original.GetLayerName(t.GetLayer()) in a.power_layer and t.GetNetname()!='GND':
            raise RuntimeError('Foreign signal/power track cuts the dedicated ground plane')
    # SES intentionally contains no zones. Keep the original board's zones and
    # keepouts, then let native KiCad refill and check the final connectivity.
    # Remove genuinely disconnected fill polygons rather than emitting floating
    # copper islands. Connected ground copper and all electrical nodes remain.
    for z in original.Zones():
        if not z.GetIsRuleArea():z.SetIslandRemovalMode(k.ISLAND_REMOVAL_MODE_ALWAYS)
    k.SaveBoard(str(pcb),original)
    # pcbnew SaveBoard can serialize its imported project defaults. Restore the
    # explicit design constraints from the real project before native DRC.
    shutil.copy2(project_file,out/project_file.name)
    drc=out/'drc.json'
    drc_command=[str(a.cli),'pcb','drc','--format','json','--all-track-errors',
                 '--schematic-parity','--refill-zones','--save-board','--severity-all',
                 '--exit-code-violations','--output',str(drc),str(pcb)]
    with (out/'drc.log').open('w') as log:
        dr=subprocess.run(drc_command,stdout=log,stderr=subprocess.STDOUT,timeout=180,
                          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    parity_ran='Failed to fetch schematic netlist' not in (out/'drc.log').read_text()
    data=json.loads(drc.read_text()) if drc.exists() else {}
    counts={key:len(data.get(key,[])) for key in ['violations','unconnected_items','schematic_parity']}
    report={'source':str(source),'output':str(pcb),'routing_command':command,
            'routing_rules':rules,'component_poses_unchanged':same_poses,
            'locked_copper_preserved':not missing,'protected_items':sum(locked.values()),
            'dsn_subgrid_rounding_restored':quantization,
            'native_drc_exit':dr.returncode,'native_drc_counts':counts,
            'native_schematic_parity_executed':parity_ran,
            'passed':dr.returncode==0 and parity_ran and not any(counts.values())}
    (out/'route-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':run()
