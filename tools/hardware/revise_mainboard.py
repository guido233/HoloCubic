#!/usr/bin/env python3
"""Naive RevB PCB transformation, run using KiCad's Python with pcbnew.

Input must be the untouched native KiCad import. Uses embedded original footprints
and bundled KiCad10 manufacturer land patterns. Outputs PCB plus local footprint
library and exact pin/net manifest. Full rebuilds intentionally discard old signal
routing and seed locked converter, feedback, RF and power trunk copper. Finish
routing with route_copy.py and require native KiCad DRC plus schematic parity.

Use --metadata-only --input <routed board> --netlist <fresh XML> to synchronize
part numbers or NC identifiers without rebuilding geometry or copper. Always
run bundled Python with -B to avoid altering the signed KiCad application.
No DRC exclusions are introduced.
"""
import argparse,json,math,re,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as k
ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'1.Hardware/RevB-KiCad/Naive/MainBoard'
TEMPLATES={}
LIBROOT=None  # explicit --libraries avoids machine-specific installed paths
LIB=DEST/'HoloCubic_RevB.pretty'
mm=k.FromMM
vec=lambda x,y:k.VECTOR2I(mm(x),mm(y))
def fp_lines(f,coords,layer,width=.05):
 for a,b in zip(coords,coords[1:]+coords[:1]):
  s=k.PCB_SHAPE(f);s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(vec(*a));s.SetEnd(vec(*b));s.SetLayer(layer);s.SetWidth(mm(width));f.Add(s)
def custom(name,pads,body,desc):
 f=k.FOOTPRINT(None);f.SetReference('REF**');f.SetValue(name);f.SetLibDescription(desc);f.SetAttributes(k.FP_SMD)
 for n,x,y,w,h in pads:
  p=k.PAD(f);p.SetNumber(str(n));p.SetAttribute(k.PAD_ATTRIB_SMD);p.SetShape(k.PAD_SHAPE_ROUNDRECT);p.SetRoundRectRadiusRatio(.15);p.SetPosition(vec(x,y));p.SetSize(vec(w,h));p.SetLayerSet(k.PAD.SMDMask());f.Add(p)
 x,y=body;fp_lines(f,[(-x/2,-y/2),(x/2,-y/2),(x/2,y/2),(-x/2,y/2)],k.F_Fab,.1)
 outerx=max(x/2,max(abs(p[1])+p[3]/2 for p in pads))+.25;outery=max(y/2,max(abs(p[2])+p[4]/2 for p in pads))+.25
 fp_lines(f,[(-outerx,-outery),(outerx,-outery),(outerx,outery),(-outerx,outery)],k.F_CrtYd)
 f.SetFPID(k.LIB_ID('HoloCubic_RevB',name));TEMPLATES[name]=f;return f

def sync_metadata(b,netlist,schematic,strict=False):
 """Sync actualXML fields,paths and NC identifiers without alteringrouting."""
 nets={n.GetNetname():n for n in b.GetNetsByName().values()}
 def net(name):
  if name not in nets:
   n=k.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
  return nets[name]
 nx=ET.parse(netlist).getroot()
 counts={}
 for fp in b.GetFootprints():
  for pd in fp.Pads():counts[pd.GetNetname()]=counts.get(pd.GetNetname(),0)+1
 if strict and {c.get('ref') for c in nx.findall('./components/comp')}!={f.GetReference() for f in b.GetFootprints()}:
  raise ValueError('Component set changed; use full rebuild and reroute')
 suuid=re.search(r'\(uuid\s+"?([0-9a-fA-F-]{36})', schematic.read_text()).group(1)
 for c in nx.findall('./components/comp'):
  f=b.FindFootprintByReference(c.get('ref'))
  if not f:raise RuntimeError('MissingPCBcomponent '+c.get('ref'))
  if strict and c.findtext('footprint')!=f.GetFPID().GetUniStringLibId():
   raise ValueError('Footprint changed for '+c.get('ref')+'; use full rebuild and reroute')
  f.SetValue(c.findtext('value',''));f.SetPath(k.KIID_PATH('/'+suuid+'/'+c.findtext('tstamps')))
  f.SetSheetfile('MainBoard.kicad_sch');f.SetSheetname('MainBoard')
  fields={ff.get('name'):(ff.text or '') for ff in c.findall('./fields/field')}
  for key in sorted(set(fields)-{'Footprint','Value','Reference'} | {'MPN','DesignNote','Datasheet','Description'}):
   f.SetField(key,fields.get(key,''));f.GetField(key).SetVisible(False)
 for nn in nx.findall('./nets/net'):
  for nd in nn.findall('node'):
   f=b.FindFootprintByReference(nd.get('ref'))
   for pd in f.Pads():
    if pd.GetNumber()==nd.get('pin'):
     target=nn.get('name').replace('/','{slash}') if nn.get('name').startswith('unconnected-') else nn.get('name')
     old=pd.GetNetname()
     if strict and target!=old and not(target.startswith('unconnected-') and counts.get(old,0)<=1):
      raise ValueError('Functional net changed at '+f.GetReference()+'.'+pd.GetNumber()+'; use full rebuild and reroute')
     pd.SetNet(net(target))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--libraries',help='KiCad footprint library directory,requiredforfullrebuild');ap.add_argument('--metadata-only',action='store_true',help='Preserverouting;onlysyncactualXMLfieldsandNCnets');ap.add_argument('--netlist',required=True,help='Fresh kicad-cli XML netlist from MainBoard.kicad_sch');ap.add_argument('--output',default=str(DEST/'MainBoard.kicad_pcb'));args=ap.parse_args()
 global LIBROOT
 if args.metadata_only:
  pro=DEST/'MainBoard.kicad_pro';saved=pro.read_bytes()
  b=k.LoadBoard(args.input);sync_metadata(b,args.netlist,DEST/'MainBoard.kicad_sch',strict=True)
  k.SaveBoard(args.output,b)
  if pro.read_bytes()!=saved:pro.write_bytes(saved)
  print('Metadata synced; componentgeometryandcopperpreserved:',args.output)
  return
 if not args.libraries:ap.error('--libraries is required for a full rebuild')
 LIBROOT=Path(args.libraries)
 b=k.LoadBoard(args.input);LIB.mkdir(exist_ok=True)
 removed_objects=[]
 def remove(obj):
  removed_objects.append(obj);b.Remove(obj)
 m=json.loads((DEST/'revb_main_manifest.json').read_text());nets={n.GetNetname():n for n in b.GetNetsByName().values()}
 def net(name):
  if name is None:return b.FindNet(0)
  if name not in nets:
   n=k.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
  return nets[name]
 def remove_net_copper(names):
  for t in list(b.GetTracks()):
   if t.GetNetname() in names:remove(t)
  for i in range(len(b.Zones())-1,-1,-1):
   z=b.Zones()[i]
   if not z.GetIsRuleArea() and z.GetNetname() in names:remove(z)
 # Imported teardrops retain obsolete pad coordinates/0.5mm local clearance.
 # Remove them when replacing the topology; actual tracks remain source-of-truth.
 for z in list(b.Zones()):
  if z.IsTeardropArea():remove(z)
 # Nearly all interfaces are repositioned or gain protection: rebuild their
 # routing rather than retaining obsolete track endpoints through new pads.
 for t in list(b.GetTracks()):
  if t.GetNetname() not in ['NetA1_1','GND']:remove(t)
 # Existing5V must be split at the new switch, and the bypass net disappears.
 remove_net_copper({'VDD_5V','NetC3_2'})
 # Preserve original signal copper except the old direct GPIO27-to-LED link,
 # whose complete net is rerouted via AHCT input and separate DIN output.
 remove_net_copper({'GPIO27','3V3','3V3A','EN','NetC8_1','NetR4_2','NetR5_2','DTR','RTS','GPIO0','USB-PWR-DP','USB-PWR-DM','GPIO4','GPIO5','GPIO23','GPIO18','DC'})
 placements={
  'A1':(143.5227,115.3541,180),
  'C1':(140.7, 96.5, 270),
  'C13':(156.7, 94.5, 0),
  'C15':(158.81, 110.55, 0),
  'C16':(149.22, 98.04, 180),
  'C17':(155.9, 111.6, 90),
  'C18':(153.37, 99.83, 0),
  'C2':(146.4, 98.92, 0),
  'C20':(154.6, 101.4, 90),
  'C21':(159.3, 94.8, 0),
  'C22':(154.8, 107.59, 90),
  'C23':(149.75, 100.27, 270),
  'C24':(158.8, 99.18, 0),
  'C3':(142.5, 94.6, 180),
  'C4':(157.5, 115.65, 0),
  'C7':(142.0, 110.0, 0),
  'CON1':(143.9545, 104.7163, 90),
  'D2':(154.9, 103.02, 90),
  'J1':(149.53164, 105.3112, 270),
  'L1':(146.25, 95.95, 270),
  'R1':(156, 94.2, 0),
  'R11':(156, 95.2, 0),
  'R12':(150, 96.2, 0),
  'R13':(152, 96.2, 0),
  'R14':(154, 96.2, 0),
  'R15':(150, 97.15, 0),
  'R16':(152, 95.2, 0),
  'R17':(154, 95.2, 0),
  'R18':(148, 94.2, 0),
  'R19':(156, 97.15, 0),
  'R2':(155.8, 113.75, 90),
  'R20':(156, 96.2, 0),
  'U2':(142.8, 97.0, 0),
  'U6':(158.45, 112.9, 0),
  'U7':(152.4, 101.16, 90),
  'U8':(158.9, 96.95, 90),
  'USB1':(160.06617, 104.9909, 90),
  'VT1':(142.1, 112.2, 90),
  'VT2':(145.7, 112.2, 90),
 }
 custom('CA_C03_RevB_Engineering_Lands',[('1',-2.675,0,1.35,2.2),('2',2.55135,0,1.1027,2.2)],(5.0,2.0),
  'CA-C03 engineeringland;toeclipped0.020mmtohold250umboardclearance;notvendornominalland;assemblyandVNAqualificationrequired.')
 for pad in TEMPLATES['CA_C03_RevB_Engineering_Lands'].Pads():pad.SetShape(k.PAD_SHAPE_RECT)
 custom('SOT23_Diodes_Recommended',[('1',-.95,1.0,.8,.9),('2',.95,1.0,.8,.9),('3',0,-1.0,.8,.9)],(3.0,1.4),
  'DiodesMMBT3904DS30036Rev27-2March2025p6:X0.8Y0.9C2.0X1outerhalf1.35Y1outer2.9; B1E2C3.')
 custom('L_TDK_VLS3012HBX',[('1',-1.05,0,1.0,3.4),('2',1.05,0,1.0,3.4)],(3,3),
  'TDK VLS3012HBX recommended lands1.0x3.4mm,gap1.1mm; TDKofficialcatalogp3.')
 custom('TI_DPY0002A',[('1',-.35,0,.3,.5),('2',.35,0,.3,.5)],(1,.6),
  'TI DPY0002A datasheet landdrawing4224561/C2024:0.3x0.5lands0.7pitch.')
 modified={p['ref']:p for p in m['parts']}
 for ref in m.get('remove_refs',[]):
  old=b.FindFootprintByReference(ref)
  if old:remove(old)
 for item in m['parts']:
  ref=item['ref'];old=b.FindFootprintByReference(ref)
  if old:remove(old)
  libid,name=item.get('source_footprint',item['footprint']).split(':')
  f=k.Cast_to_FOOTPRINT(TEMPLATES[name].Duplicate(False)) if libid=='HoloCubic_RevB' else k.FootprintLoad(str(LIBROOT/(libid+'.pretty')),name)
  if not f:raise RuntimeError(item['footprint'])
  missing=set(item['pins'])-{p.GetNumber() for p in f.Pads()}
  if missing:raise RuntimeError('Missing footprint pads '+ref+': '+str(sorted(missing)))
  if ref=='J1':
   # Restore the complete vendor pin8 land; KiCad stock crops its outertoe0.10mm.
   p8=next(p for p in f.Pads() if p.GetNumber()=='8');p8.SetPosition(vec(4.595,-5.45));p8.SetSize(vec(.85,1.10))
  f.SetReference(ref);f.SetValue(item['value']);f.SetField('MPN',item['mpn']);f.SetField('Datasheet','See revb_power_plan and manufacturer documentation')
  b.Add(f);x,y,a=placements[ref];f.SetPosition(vec(x,y))
  if ref=='J1':f.Flip(f.GetPosition(),False)
  f.SetOrientationDegrees(a)
  for p in f.Pads():
   if p.GetNumber()=='' and (not p.IsOnLayer(k.F_Cu) or p.GetAttribute()==k.PAD_ATTRIB_NPTH):continue
   if p.GetNumber() not in item['pins']:raise RuntimeError((ref,p.GetNumber()))
   p.SetNet(net(item['pins'][p.GetNumber()]));p.SetLocalSolderMaskMargin(mm(.025))
  for field in f.GetFields():field.SetVisible(False)
  item['placement_mm']=[x,y,a]
 # Existing small passives repositioned around the new power footprint.
 for ref,x,y,a in [('R6',144.5,110.05,0),('C5',146.4,110.05,0),('C6',148.9,103.8,90),('C8',149.6,102.0,180),('C10',148.9,105.6,90),('C11',155.2,97.7,90),('U3',151.9427,105.0171,180),('U4',151.4475,112.2045,90),('R3',148.9,100.2,90),('C9',151.2,108.08,0)]:
  f=b.FindFootprintByReference(ref);f.SetPosition(vec(x,y));f.SetOrientationDegrees(a)
 bottom_placements={'R7': (150, 94.2), 'R8': (152, 94.2), 'R9': (154, 94.2), 'R10': (150, 95.2), 'R16': (152, 95.2), 'R17': (154, 95.2), 'R12': (150, 96.2), 'R13': (152, 96.2), 'R14': (154, 96.2), 'R15': (150, 97.15), 'R4': (152, 97.15), 'R5': (154, 97.15), 'R1': (156, 94.2), 'R11': (156, 95.2), 'R20': (156, 96.2), 'R19': (156, 97.15), 'R18': (148, 94.2)}
 for ref,(x,y) in bottom_placements.items():
  f=b.FindFootprintByReference(ref);f.SetPosition(vec(x,y))
  if f.GetLayer()!=k.B_Cu:f.Flip(f.GetPosition(),False)
  f.SetOrientationDegrees(0)
 c16=b.FindFootprintByReference('C16');c16.Flip(c16.GetPosition(),False);c16.SetOrientationDegrees(180)
 # Correct existing pad nets.
 for ref,pins in m['existing_pin_changes'].items():
  f=b.FindFootprintByReference(ref)
  for p in f.Pads():
   if p.GetNumber() in pins:p.SetNet(net(pins[p.GetNumber()]))
 b.FindFootprintByReference('USB1').SetValue('USB4105-GF-A')
 b.FindFootprintByReference('D1').SetValue('WS2812B-V5/W');b.FindFootprintByReference('D1').SetField('MPN','WS2812B-V5/W')
 # Localmodelassets areexplicitlyregistered; antenna is amaxbodyenvelope,
 # nottheunrelatedhistoricRAINSUNmodelandnotanexactvendormodel.
 for ref,filename in [('A1','CA-C03_MaxBody_Bounding_Envelope.step'),('J1','Molex_1040310811_KiCad_F_frame.step')]:
  f=b.FindFootprintByReference(ref);f.Models().clear();model=k.FP_3DMODEL();model.m_Filename='${KIPRJMOD}/3dmodels/'+filename;f.Add3DModel(model)
 # Exact MPU-center removal, including all six in-pad GND vias.
 u3=b.FindFootprintByReference('U3');cx,cy=[k.ToMM(v) for v in (u3.GetPosition().x,u3.GetPosition().y)]
 for p in list(u3.Pads()):
  if p.GetNumber()=='' and p.GetNetname()=='GND':
   removed_objects.append(p);u3.Remove(p)
 removed=0
 for t in list(b.GetTracks()):
  if isinstance(t,k.PCB_VIA) and abs(k.ToMM(t.GetPosition().x)-151.1427)<1.35 and abs(k.ToMM(t.GetPosition().y)-105.0671)<1.4:
   remove(t);removed+=1
 assert removed==6,removed
 z=k.ZONE(b);z.SetIsRuleArea(True);z.SetLayer(k.F_Cu);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(False)
 poly=z.Outline();poly.NewOutline()
 for x,y in [(cx-1.4,cy-1.45),(cx+1.4,cy-1.45),(cx+1.4,cy+1.45),(cx-1.4,cy+1.45)]:poly.Append(mm(x),mm(y))
 b.Add(z)
 # Recreate ground connectivity, rather than leaving old GND stitching vias
 # underneath new signal pads (which connectivity may reassign to other nets).
 for t in list(b.GetTracks()):
  if t.GetNetname()!='NetA1_1':remove(t)
 # Upgrade the legacy plated-via annular rings, rather than lowering the rule.
 for t in b.GetTracks():
  if isinstance(t,k.PCB_VIA):t.SetWidth(max(t.GetWidth(),t.GetDrillValue()+mm(.2)))
 # USB plastic locating pegs are nonplated holes, not copper-less PTH pads.
 for p in b.FindFootprintByReference('USB1').Pads():
  if p.GetNumber()=='0' and p.GetDrillSize().x>0 and p.GetNetCode()==0:
   p.SetAttribute(k.PAD_ATTRIB_NPTH);p.SetLayerSet(k.PAD.UnplatedHoleMask())
 # Keep fine-pitch mask webs manufacturable (old importer applied76um expansion).
 for f in b.GetFootprints():
  for p in f.Pads():
   if p.GetAttribute()==k.PAD_ATTRIB_SMD:p.SetLocalSolderMaskMargin(mm(.025))
 # ESP32-PICO officialv1.5 Fig16/17pp59/60: pad0 is physicalmanufacturer49GND.
 # Copper4.5mm, maskdefined4.0mm, 21 thermalholes between16pastewindows.
 u4=b.FindFootprintByReference('U4');ep=next(p for p in u4.Pads() if p.GetNumber()=='0')
 ep.SetSize(vec(4.5,4.5));ep.SetShape(k.PAD_SHAPE_CHAMFERED_RECT);ep.SetChamferPositions(1);ep.SetChamferRectRatio(.5/4.5);ep.SetRoundRectRadiusRatio(.05/4.5)
 ep.SetLocalSolderMaskMargin(mm(-.25));ls=ep.GetLayerSet();ls.RemoveLayer(k.F_Paste);ep.SetLayerSet(ls);ep.SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
 for dx in [-1.575,-.525,.525,1.575]:
  for dy in [-1.575,-.525,.525,1.575]:
   pa=k.PAD(u4);pa.SetNumber('');pa.SetAttribute(k.PAD_ATTRIB_SMD);pa.SetShape(k.PAD_SHAPE_RECT);pa.SetSize(vec(.75,.75));pa.SetPosition(vec(151.4475+dx,112.2045+dy));pls=k.LSET();pls.AddLayer(k.F_Paste);pa.SetLayerSet(pls);u4.Add(pa)
 for dx in [-2,-1.05,0,1.05,2]:
  for dy in [-2,-1.05,0,1.05,2]:
   if abs(dx)==2 and abs(dy)==2:continue
   v=k.PCB_VIA(b);v.SetPosition(vec(151.4475+dx,112.2045+dy));v.SetWidth(mm(.46));v.SetDrill(mm(.25));v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net('GND'));v.SetLocked(True);v.SetFrontTentingMode(k.TENTING_MODE_TENTED);v.SetBackTentingMode(k.TENTING_MODE_TENTED);b.Add(v)
 # A dense-assembly0402 courtyard uses the actual pad/body envelope +0.10mm.
 # Other manufacturer courtyards stay intact. This is physical geometry, not a DRC exclusion.
 for f in b.GetFootprints():
  if f.GetReference() in modified and modified[f.GetReference()]['mpn'].startswith(('RC0402','GRM155')):
   for g in list(f.GraphicalItems()):
    if g.GetLayer() in [k.F_CrtYd,k.B_CrtYd]:
     removed_objects.append(g);f.Remove(g)
   pp=[p.GetBoundingBox() for p in f.Pads() if p.IsOnLayer(f.GetLayer())]
   xmin=min(k.ToMM(q.GetLeft()) for q in pp)-.1;xmax=max(k.ToMM(q.GetRight()) for q in pp)+.1
   ymin=min(k.ToMM(q.GetTop()) for q in pp)-.1;ymax=max(k.ToMM(q.GetBottom()) for q in pp)+.1
   fp_lines(f,[(xmin,ymin),(xmax,ymin),(xmax,ymax),(xmin,ymax)],k.F_CrtYd if f.GetLayer()==k.F_Cu else k.B_CrtYd)
 # Closed connector courtyard independently derived from each supplier STEP
 # solid and all pads, each expanded0.25mm. Keep open-latch validation separate.
 cpoly=ROOT/'tools/hardware/data/fh12_closed_courtyard.json'
 if cpoly.exists():
  f=b.FindFootprintByReference('CON1')
  for g in list(f.GraphicalItems()):
   if g.GetLayer()==k.F_CrtYd:removed_objects.append(g);f.Remove(g)
  x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y);a=math.radians(-f.GetOrientationDegrees())
  points=[(x+px*math.cos(a)-py*math.sin(a),y+px*math.sin(a)+py*math.cos(a)) for px,py in json.loads(cpoly.read_text())['polygon_local_xy_mm']]
  fp_lines(f,points,k.F_CrtYd)
 upoly=ROOT/'tools/hardware/data/usb4105_closed_courtyard.json'
 f=b.FindFootprintByReference('USB1')
 for g in list(f.GraphicalItems()):
  if g.GetLayer()==k.F_CrtYd:removed_objects.append(g);f.Remove(g)
 points=json.loads(upoly.read_text())['polygon_local_xy_mm']
 x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y);a=math.radians(-f.GetOrientationDegrees())
 fp_lines(f,[(x+px*math.cos(a)-py*math.sin(a),y+px*math.sin(a)+py*math.cos(a)) for px,py in points],k.F_CrtYd)
 # Molex courtyard: actualregisteredSTEPprojectedoutline+completevendorlands,
 # offset0.255/simplify0.001/mesh0.002 keepsminimum0.25margin; Bfliplocalcoords.
 f=b.FindFootprintByReference('J1')
 for g in list(f.GraphicalItems()):
  if g.GetLayer()==k.B_CrtYd:removed_objects.append(g);f.Remove(g)
 points=json.loads((ROOT/'tools/hardware/data/molex104031_closed_courtyard.json').read_text())['polygon_local_xy_mm']
 x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y);a=math.radians(-f.GetOrientationDegrees())
 fp_lines(f,[(x+px*math.cos(a)-py*math.sin(a),y+px*math.sin(a)+py*math.cos(a)) for px,py in points],k.B_CrtYd)
 # TPS22918 manufacturer maxbody +actualpads,each expanded0.25mm.
 # Its rectangular stock courtyard includes empty corners beside the USB slot.
 f=b.FindFootprintByReference('U6')
 for g in list(f.GraphicalItems()):
  if g.GetLayer()==k.F_CrtYd:removed_objects.append(g);f.Remove(g)
 union=k.SHAPE_POLY_SET();rects=[(158.45-.875-.25,112.9-1.525-.25,158.45+.875+.25,112.9+1.525+.25)]
 for p in f.Pads():
  q=p.GetBoundingBox();rects.append(tuple(k.ToMM(v)+d for v,d in zip([q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()],[-.25,-.25,.25,.25])))
 for x1,y1,x2,y2 in rects:
  q=k.SHAPE_POLY_SET();q.NewOutline()
  for xx,yy in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]:q.Append(mm(xx),mm(yy))
  union.BooleanAdd(q)
 for i in range(union.OutlineCount()):
  ch=union.COutline(i);fp_lines(f,[(k.ToMM(ch.CPoint(n).x),k.ToMM(ch.CPoint(n).y)) for n in range(ch.PointCount())],k.F_CrtYd)
 # Lock RF and hand-routed switching/converter feedback paths before autoroute.
 def pp(ref,num):
  return next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber()==str(num))
 def xy(p):return (k.ToMM(p.GetPosition().x),k.ToMM(p.GetPosition().y))
 def track(n,points,width=.4,layer=k.F_Cu):
  for a,z in zip(points,points[1:]):
   t=k.PCB_TRACK(b);t.SetStart(vec(*a));t.SetEnd(vec(*z));t.SetWidth(mm(width));t.SetLayer(layer);t.SetNet(net(n));t.SetLocked(True);b.Add(t)
 def via(n,x,y,diameter=.6,drill=.3):
  v=k.PCB_VIA(b);v.SetPosition(vec(x,y));v.SetWidth(mm(diameter));v.SetDrill(mm(drill));v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net(n));v.SetLocked(True);b.Add(v)
 for t in b.GetTracks():
  if t.GetNetname()=='NetA1_1':t.SetLocked(True)
 track('BUCK_SW',[xy(pp('U2',7)),(144.3,96.75),(144.3,95.35),(144.75,94.9)],.24)
 track('BUCK_SW',[(144.75,94.9),xy(pp('L1',1))],.4)
 track('3V3',[xy(pp('L1',2)),(147.425,97.0),xy(pp('C2',2))],.6)
 track('3V3',[xy(pp('U2',6)),(144.275,97.25),(144.275,99.86),(147.425,99.86),xy(pp('C2',2))],.15)
 track('GND',[xy(pp('C1',1)),(141.1,96.0),(141.35,96.25)],.3)
 track('GND',[(141.35,96.25),xy(pp('U2',1))],.25)
 track('VDD_5V',[xy(pp('C1',2)),(141.1,97.0),(141.35,96.75)],.3)
 track('VDD_5V',[(141.35,96.75),xy(pp('U2',2)),xy(pp('U2',3))],.25)
 via('VDD_5V',141.475,95.55);track('VDD_5V',[xy(pp('C3',2)),(141.475,95.55)],.5)
 via('VDD_5V',140.7,97.8);track('VDD_5V',[xy(pp('C1',2)),(140.7,97.8)],.4)
 track('VDD_5V',[(141.475,95.55),(140.7,96.325),(140.7,97.8)],.5,k.B_Cu)
 # CT timingnode onB clearofSW andUSB; keepGND referenceandqualifycrosstalk.
 via('LOAD_CT',159.95,114.49)
 track('LOAD_CT',[xy(pp('C16',1)),(158.5,98.04),(158.5,112.2),(159.95,113.65),(159.95,114.49)],.15,k.B_Cu)
 track('LOAD_CT',[xy(pp('U6',4)),(159.95,114.49)],.15)
 # A locked0.6mm distribution trunk feeds SD/FFC and the MCU branch.
 # This prevents the router treating the thin Kelvin sense loop as a power bus.
 via('3V3',148.0,99.8)
 track('3V3',[xy(pp('C2',2)),(148.0,99.495),(148.0,99.8)],.5)
 track('3V3',[(148.0,99.8),(148.0,97.25),(142.0,97.25),(142.0,103.4663),(141.0,103.4663)],.6,k.B_Cu)
 via('3V3',141.0,103.4663);track('3V3',[(141.0,103.4663),xy(pp('CON1',7))],.4)
 track('3V3',[(148.0,99.8),(148.0,114.9),(155.0,114.9),(155.6,115.5)],.6,k.B_Cu)
 track('3V3',[(148.0,105.5062),(146.0,105.5062),xy(pp('J1',4))],.4,k.B_Cu)
 # ESP32supplybackbone is handrouted andlocked. Fourmillocalpinnecks
 # are NOT substituted for thehighcurrentpath: maincopper0.4mm andpairedvias.
 # Blefttrunk feeds37/43/46; southernFinnerrail bypassesRFpin2withoutmovingRF.
 for pin in [37,43,46]:
  y=109.6 if pin==37 else xy(pp('U4',pin))[1];via('3V3A',148.7,y,.46,.25);track('3V3A',[xy(pp('U4',pin)),(148.7,y)],.25)
 track('3V3A',[(148.7,109.6),(148.7,113.9545)],.4,k.B_Cu)
 track('3V3A',[(148.7,113.9545),(148.7,115.567),xy(pp('U4',1))],.25)
 track('3V3A',[(148.7,114.9),(150.1975,114.9)],.3)
 for pin in [3,4]:track('3V3A',[xy(pp('U4',pin)),(xy(pp('U4',pin))[0],114.9)],.25)
 # Two21milvias inparallel bridge thetoprailaroundtheMPU/cardandsustain0.5A.
 for x in [153.05,153.8]:via('3V3A',x,109.55,.46,.25)
 track('3V3A',[(148.7,109.6),(153.05,109.6),(153.05,109.55),(153.8,109.55)],.4,k.B_Cu)
 track('3V3A',[(153.05,109.55),(153.8,109.55),(154.13,109.88),(154.13,111.9545)],.4)
 via('3V3A',154.13,111.9545);track('3V3A',[(154.13,111.9545),xy(pp('U4',19))],.25)
 via('3V3A',155.8,112.85);track('3V3A',[(155.8,112.85),xy(pp('R2',2))],.3)
 track('3V3A',[(155.8,112.85),(154.9045,111.9545),(154.13,111.9545)],.4,k.B_Cu)
 # C4bulk andC5fastbypass connect tothatbackbone,witha1.45mm0.24mmcapneck.
 track('3V3A',[xy(pp('C4',2)),(158.45,114.55),(156.5,114.55)],.4)
 track('3V3A',[(156.5,114.55),(156.4,114.45),(156.4,113.24),xy(pp('R2',2))],.24)
 track('3V3A',[xy(pp('C5',2)),(147.3,110.05),(147.3,109.4545),xy(pp('U4',37))],.25)
 via('3V3',155.6,115.5);track('3V3',[xy(pp('R2',1)),(155.6,115.5)],.3)
 # SlowCTroute hasgroundguard andcontinuousgroundreference inthereturnplane.
 track('GND',[(158.95,98.7),(158.95,110.6)],.15,k.B_Cu)
 # FullDMescape fromCP2102toESD andbothUSBcontacts;460/250signalvias.
 via('USB-PWR-DM',151.9,99.9047,.46,.25)
 track('USB-PWR-DM',[xy(pp('U1',5)),(152.4047,99.4),(151.9,99.9047)],.1016)
 via('USB-PWR-DM',150.5,101.15,.46,.25)
 track('USB-PWR-DM',[xy(pp('U7',2)),(151.9,102.03),(150.7,102.03),(150.7,101.35),(150.5,101.15)],.1016)
 track('USB-PWR-DM',[(151.9,99.9047),(151.9,100.6),(151.35,101.15),(150.5,101.15)],.15,k.B_Cu)
 for pin in ['A7','B7']:
  y=xy(pp('USB1',pin))[1];via('USB-PWR-DM',155.3,y,.46,.25);track('USB-PWR-DM',[xy(pp('USB1',pin)),(155.3,y)],.15)
 track('USB-PWR-DM',[(155.3,105.7409),(155.3,104.7409),(153.35,104.7409),(153.35,101.15),(150.5,101.15)],.15,k.B_Cu)
 track('3V3A',[xy(pp('R6',1)),(143.992,109.46),(146.908,109.46),xy(pp('C5',2))],.1016)
 # CC1 gets a realfree escape, notablockedpad; remainingpath may crosslayers.
 via('USB_CC1',153.86,102.45,.46,.25)
 track('USB_CC1',[xy(pp('U7',4)),(152.9,102.03),(153.86,102.03),(153.86,102.45)],.1016)
 via('USB_CC1',148.6,96.2,.46,.25);track('USB_CC1',[xy(pp('R12',1)),(148.6,96.2)],.15,k.B_Cu)
 # MPU-6050REGOUT localcapacitor fullyconnected belowtheUSBescape corridor.
 track('NetC8_1',[xy(pp('C8',1)),(150.15,102.38),(151.6927,102.38),xy(pp('U3',10))],.1016)
 via('GND',143.525,95.55);track('GND',[xy(pp('C3',1)),(143.525,95.55)],.5)
 via('GND',142.8,98.4);track('GND',[xy(pp('U2',9)),(142.8,98.4)],.7)
 via('GND',145.375,98.0);track('GND',[xy(pp('C2',1)),(145.375,98.0)],.5)
 for num in [1,4,5,9]:pp('U2',num).SetLocalZoneConnection(k.ZONE_CONNECTION_FULL)
 # Keep dense legacy assembly graphics on fabrication layers; external silk
 # must stay clear of exposed copper and the board edge. MPN fields stay hidden.
 for f in b.GetFootprints():
  for field in f.GetFields():
   field.SetVisible(False)
   field.SetLayer(k.F_Fab if f.GetLayer()==k.F_Cu else k.B_Fab)
  f.Reference().SetVisible(True);f.Reference().SetPosition(f.GetPosition());f.Reference().SetTextSize(vec(.6,.6));f.Reference().SetTextThickness(mm(.1));f.Reference().SetLayer(k.F_Fab if f.GetLayer()==k.F_Cu else k.B_Fab)
  for g in f.GraphicalItems():
   if g.GetLayer() in [k.F_SilkS,k.B_SilkS]:g.SetLayer(k.F_Fab if g.GetLayer()==k.F_SilkS else k.B_Fab)
 for d in b.GetDrawings():
  if d.GetLayer() in [k.F_SilkS,k.B_SilkS]:d.SetLayer(k.F_Fab if d.GetLayer()==k.F_SilkS else k.B_Fab)
 # Bundle every footprint, including original nonstandard connector geometries.
 for f in b.GetFootprints():
  oldid=f.GetFPID();name=('RevB_'+f.GetReference()) if f.GetReference() in modified or f.GetReference()=='U4' else 'Original_'+f.GetReference()
  f.SetFPID(k.LIB_ID('HoloCubic_RevB',name));copy=k.Cast_to_FOOTPRINT(f.Duplicate(False))
  if copy.GetLayer()==k.B_Cu:copy.Flip(copy.GetPosition(),False)
  copy.SetOrientationDegrees(0);copy.SetPosition(vec(0,0))
  for p in copy.Pads():p.SetNetCode(0)
  k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(LIB),copy)
  if f.GetReference() in modified:modified[f.GetReference()]['footprint']='HoloCubic_RevB:'+name
  else:m.setdefault('existing_footprints',{})[f.GetReference()]='HoloCubic_RevB:'+name
 sync_metadata(b,args.netlist,DEST/'MainBoard.kicad_sch')
 # Minimal explicit fabrication limits; no exclusions or disabled checks.
 ds=b.GetDesignSettings();ds.m_TrackMinWidth=mm(.1016);ds.m_MinClearance=mm(.127);ds.m_CopperEdgeClearance=mm(.25);ds.m_MinThroughDrill=mm(.25);ds.m_ViasMinSize=mm(.45);ds.m_ViasMinAnnularWidth=mm(.1);ds.m_HoleClearance=mm(.19);ds.m_SolderMaskMinWidth=mm(.075);ds.m_SolderMaskExpansion=mm(.025)
 b.BuildConnectivity();k.SaveBoard(args.output,b)
 (DEST/'MainBoard.kicad_dru').write_text('''(version 1)
(rule "General hole to copper clearance 0.20mm"
  (constraint hole_clearance (min 0.20mm)))
(rule "GCT USB4105 vendor internal NPTH to land 0.1944mm"
  (condition "A.memberOfFootprint('USB1') && B.memberOfFootprint('USB1')")
  (constraint hole_clearance (min 0.19mm)))
''')
 (DEST/'fp-lib-table').write_text('(fp_lib_table\n  (version 7)\n  (lib (name "HoloCubic_RevB")(type "KiCad")(uri "${KIPRJMOD}/HoloCubic_RevB.pretty")(options "")(descr "Embedded Naive originals and RevB verified manufacturer lands"))\n)\n')
 m['revision']='Naive RevB placed; routing in progress';m['removed_mpu_center_vias']=removed
 used={f.GetFPID().GetUniStringLibItemName() for f in b.GetFootprints()}
 for stale in LIB.glob('*.kicad_mod'):
  if stale.stem not in used:stale.unlink()
 mapping={f.GetReference():f.GetFPID().GetUniStringLibId() for f in b.GetFootprints()}
 (DEST/'revb_footprint_map.json').write_text(json.dumps(mapping,indent=2)+'\n')
 (DEST/'revb_main_manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 # Save manufacturing rules in project JSON too, so CLI DRC loads identical limits.
 pro=DEST/'MainBoard.kicad_pro';pj=json.loads(pro.read_text());dsj=pj['board']['design_settings'];dsj['rules'].update(min_clearance=.127,min_track_width=.1016,min_via_diameter=.45,min_via_annular_width=.1,min_through_hole_diameter=.25,min_copper_edge_clearance=.25,min_hole_clearance=.19,solder_mask_min_width=.075);dsj['drc_exclusions']=[]
 pj['net_settings']['classes']=[dict(name='Default',clearance=.127,track_width=.15,via_diameter=.46,via_drill=.25,microvia_diameter=.3,microvia_drill=.1,diff_pair_width=.15,diff_pair_gap=.127,diff_pair_via_gap=.127,bus_width=12,wire_width=6,priority=2147483647,pcb_color='rgba(0,0,0,0)',schematic_color='rgba(0,0,0,0)',line_style=0,tuning_profile='')]
 power=dict(pj['net_settings']['classes'][0]);power.update(name='Power',clearance=.127,track_width=.4,via_diameter=.6,via_drill=.3,priority=0)
 pj['net_settings']['classes'].append(power)
 ground=dict(pj['net_settings']['classes'][0]);ground.update(name='Ground',priority=1)
 rf=dict(pj['net_settings']['classes'][0]);rf.update(name='RF',track_width=.254,priority=2)
 pj['net_settings']['classes'] += [ground,rf]
 pj['net_settings']['netclass_patterns']=[dict(netclass='Power',pattern=n) for n in ['USB_VBUS','VDD_5V','3V3','3V3A']]+[dict(netclass='Ground',pattern='GND'),dict(netclass='RF',pattern='NetA1_1')]
 for key in ['copper_edge_clearance','hole_clearance']:dsj['rules'].pop(key,None)
 pro.write_text(json.dumps(pj,indent=2)+'\n')
 print('Saved',args.output,'new/modified',len(modified),'MPU vias removed',removed)
if __name__=='__main__':main()
