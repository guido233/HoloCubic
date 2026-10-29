#!/usr/bin/env python3
"""Build the Naive RevB display PCB using KiCad's pcbnew Python (-B).

The original Altium/native import is read-only. The maintained PCB has an
explicit backlight current sink, a verified FFC footprint and local bypass.
Run native DRC and schematic parity after running this transformation.
"""
import argparse
import json
from pathlib import Path
import uuid
import pcbnew as k

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / '1.Hardware/RevB-KiCad/Naive/ExtendBoard'
NS = uuid.UUID('1e907dc7-a4c5-4678-8231-beef2e9bd385')
mm = k.FromMM
v = lambda x, y: k.VECTOR2I(mm(x), mm(y))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--libraries', required=True)
    args = ap.parse_args()
    manifest = json.loads((DEST / 'revb_extend_manifest.json').read_text())
    specs = {p['ref']:p for p in manifest['parts']}
    project_path=DEST/'ExtendBoard.kicad_pro'
    project_source=project_path.read_text() if project_path.exists() else None
    b = k.LoadBoard(args.input)
    lib = DEST / 'HoloCubic_Ext.pretty'
    lib.mkdir(exist_ok=True)
    stock = Path(args.libraries)
    nets = {n.GetNetname():n for n in b.GetNetsByName().values()}
    def net(name):
        if name not in nets:
            n = k.NETINFO_ITEM(b, name); b.Add(n); nets[name] = n
        return nets[name]
    retained = []
    def remove(obj):
        retained.append(obj); b.Remove(obj)
    # Start with clear copper. All nets are routed in a separate DSN/SES step,
    # followed by native KiCad DRC, netlist and geometry checks.
    for t in list(b.GetTracks()):
        remove(t)
    for z in list(b.Zones()):
        if not z.GetIsRuleArea(): remove(z)
    old = {f.GetReference():f for f in b.GetFootprints()}
    old['1'].SetReference('LCD1'); old['LCD1'] = old.pop('1')
    def load(library, name):
        f = k.FootprintLoad(str(stock / (library+'.pretty')), name)
        if f is None: raise RuntimeError('Missing library footprint '+name)
        return f
    def replacement(ref, fp):
        orig=old.get(ref)
        if orig:
            pos=orig.GetPosition(); angle=orig.GetOrientation()
            remove(orig)
        else:
            pos=v(*placements[ref][:2]);angle=k.EDA_ANGLE(placements[ref][2],k.DEGREES_T)
        b.Add(fp);fp.SetPosition(pos);fp.SetOrientation(angle);old[ref]=fp
        return fp
    placements = {'U1':(141.0,112.2,0),'R2':(144.3,111.2,90),
                  'R3':(148.0,115.0,0),'C1':(144.0,105.5,0),
                  'C2':(141.5,105.5,0),'C3':(138.5,108.5,0),
                  'C4':(138.2,106.5,0)}
    replacement('CON1', load('Connector_FFC-FPC', 'Hirose_FH12-8S-0.5SH_1x08-1MP_P0.50mm_Horizontal'))
    # AOS PO-00001N recommended lands, not a package-name-only substitution.
    q=load('Package_TO_SOT_SMD','SOT-23')
    for pad in q.Pads():
        xy={'1':(-1.2,-.95),'2':(-1.2,.95),'3':(1.2,0)}[pad.GetNumber()]
        pad.SetPosition(v(*xy));pad.SetSize(v(.8,.8));pad.SetRoundRectRadiusRatio(.125)
    for graphic in list(q.GraphicalItems()):
        if graphic.GetLayer() in [k.F_CrtYd,k.F_Fab]:
            retained.append(graphic);q.Remove(graphic)
    def rectangle(fp,box,layer):
        x1,y1,x2,y2=box;points=[(x1,y1),(x2,y1),(x2,y2),(x1,y2)]
        for a,c in zip(points,points[1:]+points[:1]):
            shape=k.PCB_SHAPE(fp);shape.SetShape(k.SHAPE_T_SEGMENT)
            shape.SetStart(v(*a));shape.SetEnd(v(*c));shape.SetLayer(layer)
            shape.SetWidth(mm(.05 if layer in [k.F_CrtYd,k.B_CrtYd] else .1));fp.Add(shape)
    rectangle(q,(-.9,-1.55,.9,1.55),k.F_Fab)
    rectangle(q,(-1.85,-1.8,1.85,1.8),k.F_CrtYd)
    replacement('Q1', q)
    replacement('R1', load('Resistor_SMD','R_0402_1005Metric'))
    replacement('U1', load('Package_TO_SOT_SMD','SOT-23-6'))
    for ref, name in [('R2','R_0603_1608Metric'),('R3','R_0402_1005Metric')]:
        replacement(ref, load('Resistor_SMD', name))
    for ref, name in [('C1','C_0402_1005Metric'),('C2','C_0603_1608Metric'),
                      ('C3','C_0402_1005Metric'),('C4','C_0603_1608Metric')]:
        replacement(ref, load('Capacitor_SMD', name))
    # Original bare panel body is on B, while the folded FPC solder pads are on F.
    # This mixed mechanical/electrical construction is intentional.
    fps={}
    for ref, spec in specs.items():
        f=old[ref];f.SetReference(ref);f.SetValue(spec['value'])
        f.SetField('MPN',spec['mpn']);f.SetField('DesignNote',spec['note'])
        sid=spec.get('uuid',str(uuid.uuid5(NS,'symbol:'+ref)))
        spec['uuid']=sid
        f.SetPath(k.KIID_PATH('/'+manifest['root_uuid']+'/'+sid))
        f.SetFPID(k.LIB_ID('HoloCubic_Ext',spec['footprint'].split(':')[1]))
        if ref=='LCD1':
            f.SetField('MechanicalStatus','P133 candidate body; folded FPC and enclosure unverified')
            rectangle(f,(154.9440,103.5719,157.4760,112.1719),k.F_CrtYd)
            rectangle(f,(133.5411,91.5736,163.4611,118.4336),k.B_CrtYd)
        for field in f.GetFields(): field.SetVisible(False)
        # Stock library model paths resolve in a normal KiCad install.
        for pad in f.Pads():
            number=pad.GetNumber()
            if number not in spec['pins']: raise ValueError('Unmapped '+ref+'.'+number)
            pad.SetNet(net(spec['pins'][number]));pad.SetLocalSolderMaskMargin(mm(.05))
            if spec['pins'][number]=='GND': pad.SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
        fps[ref]=f
        local=k.Cast_to_FOOTPRINT(f.Duplicate(False));local.SetPosition(v(0,0));local.SetOrientation(k.EDA_ANGLE(0,k.DEGREES_T))
        local.SetReference('REF**');local.SetPath(k.KIID_PATH())
        k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(lib),local)
    manifest['status']='engineering placement generated; routing, native checks and prototype validation pending'
    (DEST/'revb_extend_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (DEST/'revb_footprint_map.json').write_text(json.dumps({r:p['footprint'] for r,p in specs.items()},indent=2)+'\n')
    (DEST/'fp-lib-table').write_text('(fp_lib_table\n (version 7)\n (lib (name "HoloCubic_Ext")(type "KiCad")(uri "${KIPRJMOD}/HoloCubic_Ext.pretty")(options "")(descr "Verified and preserved RevB display footprints"))\n)\n')
    def pt(ref, pin):
        p=next(p for p in fps[ref].Pads() if p.GetNumber()==str(pin))
        return (k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y))
    def route(name, points, width=.25, layer=k.F_Cu):
        for a,c in zip(points,points[1:]):
            if a==c: continue
            t=k.PCB_TRACK(b);t.SetStart(v(*a));t.SetEnd(v(*c));t.SetWidth(mm(width));t.SetLayer(layer);t.SetNet(net(name));b.Add(t)
    def via(name, xy):
        z=k.PCB_VIA(b);z.SetPosition(v(*xy));z.SetViaType(k.VIATYPE_THROUGH);z.SetLayerPair(k.F_Cu,k.B_Cu);z.SetWidth(mm(.6));z.SetDrill(mm(.3));z.SetNet(net(name));z.SetLocked(True);b.Add(z)
    # Routing is performed by the documented external DSN/SES step.
    # Stitch both ground planes using explicit vias outside part courtyards.
    for xy in [(135,93),(161.8,93),(135,116.8),(161.8,116.8)]: via('GND',xy)
    for layer in [k.F_Cu,k.B_Cu]:
        zone=k.ZONE(b);zone.SetLayer(layer);zone.SetNet(net('GND'));zone.SetLocalClearance(mm(.127));zone.SetThermalReliefGap(mm(.2));zone.SetThermalReliefSpokeWidth(mm(.25));zone.SetMinThickness(mm(.15));zone.SetIslandRemovalMode(k.ISLAND_REMOVAL_MODE_ALWAYS)
        poly=zone.Outline();poly.NewOutline()
        for x,y in [(134.1,92.18),(162.9,92.18),(162.9,117.83),(134.1,117.83)]:poly.Append(int(mm(x)),int(mm(y)))
        b.Add(zone)
    for drawing in list(b.GetDrawings()):
        if drawing.GetLayer() in [k.F_SilkS,k.B_SilkS]: remove(drawing)
    # Correct imported layer display names and mark the engineering revision.
    b.SetLayerName(k.F_Cu,'F.Cu');b.SetLayerName(k.B_Cu,'B.Cu')
    b.GetDesignSettings().SetBoardThickness(mm(1.071118))
    k.SaveBoard(str(DEST/'ExtendBoard.kicad_pcb'),b)
    if project_source is not None:project_path.write_text(project_source)
    # The legacy LCD's body outline was on silkscreen and clipped the board.
    # Retain it on the fabrication layer in both the PCB and local library.
    from revise_schematic import parse, alln, get, write, Q
    for path in [DEST/'ExtendBoard.kicad_pcb', *lib.glob('*.kicad_mod')]:
        doc=parse(path.read_text())
        footprints=alln(doc,'footprint') if doc[0]=='kicad_pcb' else [doc]
        for fp in footprints:
            for node in fp:
                if not isinstance(node,list) or not node or not str(node[0]).startswith('fp_'): continue
                layer=get(node,'layer')
                if layer and layer[1] in ['F.SilkS','B.SilkS']:
                    layer[1]=Q('F.Fab' if layer[1]=='F.SilkS' else 'B.Fab')
        write(path,doc)
    print('Wrote',len(fps),'footprints; native DRC still required.')

if __name__=='__main__': main()
