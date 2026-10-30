#!/usr/bin/env python3
"""Apply reviewed dense-assembly geometry to an evaluation COPY of MainRevB.

Requires real supplier/body courtyard data for the closed Hirose connector.
Explicit changes:C9up0.06,C24right0.12,C18down0.02 andMuratareflowlands.
All otherpads/poses andalltracks remainexact. Run nativeDRCafterward.
"""
import argparse,json,math
from pathlib import Path
import pcbnew as k
mm=k.FromMM
V=lambda x,y:k.VECTOR2I(mm(x),mm(y))
BODY={'U1':(5.1,5.1),'U3':(4.1,4.1),'U4':(7.1,7.1),'U5':(3.1,1.7),'D1':(5.4,5.2),'D2':(1.0,.6),'C24':(1.7,.9)}
def position(f):return [k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y),f.GetOrientationDegrees(),f.GetLayer()]
def tracks(b):
 return sorted((t.m_Uuid.AsString(),t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(k.F_Cu) if isinstance(t,k.PCB_VIA) else t.GetWidth(),t.IsLocked(),t.GetDrillValue() if isinstance(t,k.PCB_VIA) else 0) for t in b.GetTracks())
def lines(f,points,layer):
 for a,z in zip(points,points[1:]+points[:1]):
  g=k.PCB_SHAPE(f);g.SetShape(k.SHAPE_T_SEGMENT);g.SetStart(V(*a));g.SetEnd(V(*z));g.SetLayer(layer);g.SetWidth(mm(.05));f.Add(g)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');ap.add_argument('--ffc-courtyard',required=True);ap.add_argument('--report',required=True);args=ap.parse_args();b=k.LoadBoard(args.input);oldtracks=tracks(b);oldposes={f.GetReference():position(f) for f in b.GetFootprints()};removed=[]
 for ref,target in [('C9',(151.2,108.02)),('C24',(158.92,99.18)),('C18',(153.37,99.85))]:b.FindFootprintByReference(ref).SetPosition(V(*target))
 c18=b.FindFootprintByReference('C18')
 # Murata exactGRM155R71C104KA88-01Ap27Table2:a=.4,b=.4,c=.5.
 for p in c18.Pads():p.SetPosition(V(153.37+(-.4 if p.GetNumber()=='1' else .4),99.85));p.SetSize(V(.4,.5))
 rebuilt=[]
 for f in b.GetFootprints():
  ref=f.GetReference();layer=k.F_CrtYd if f.GetLayer()==k.F_Cu else k.B_CrtYd
  has=any(g.GetLayer()==layer for g in f.GraphicalItems())
  if has and ref not in ['C18','C22','C24','D2','CON1']:continue
  for g in list(f.GraphicalItems()):
   if g.GetLayer() in [k.F_CrtYd,k.B_CrtYd]:removed.append(g);f.Remove(g)
  x,y=k.ToMM(f.GetPosition().x),k.ToMM(f.GetPosition().y);angle=math.radians(-f.GetOrientationDegrees())
  if ref=='CON1':
   data=json.loads(Path(args.ffc_courtyard).read_text());local=data['polygon_local_xy_mm'];pts=[(x+px*math.cos(angle)-py*math.sin(angle),y+px*math.sin(angle)+py*math.cos(angle)) for px,py in local];lines(f,pts,layer);rebuilt.append({'ref':ref,'margin_mm':.1,'basis':'fullsupplierSTEPprojection+alllands,explicitdenseassembly;closedshapeonly'});continue
  passive=ref.startswith(('R','C'));w,h=BODY.get(ref,(1.05,.55)) if passive else BODY[ref];margin=.25 if ref=='D1' else .1
  # Roundoffset is atrueEuclidean margin,notanAABBcorner excess.2umreserve
  # covers1um polygonapproximation; actualCu shapesretainroundrectcorners.
  q=k.SHAPE_POLY_SET();q.NewOutline()
  for dx,dy in [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]:q.Append(mm(x+dx*math.cos(angle)-dy*math.sin(angle)),mm(y+dx*math.sin(angle)+dy*math.cos(angle)))
  q.Inflate(mm(margin+.002),k.CORNER_STRATEGY_ROUND_ALL_CORNERS,mm(.001))
  for p in f.Pads():
   if not p.IsOnLayer(f.GetLayer()):continue
   r=k.SHAPE_POLY_SET();p.TransformShapeToPolygon(r,f.GetLayer(),mm(margin+.002),mm(.001),k.ERROR_OUTSIDE);q.BooleanAdd(r)
  for i in range(q.OutlineCount()):
   ch=q.COutline(i);pts=[(k.ToMM(ch.CPoint(n).x),k.ToMM(ch.CPoint(n).y)) for n in range(ch.PointCount())];lines(f,pts,layer)
  rebuilt.append({'ref':ref,'minimum_margin_mm':margin,'construction_margin_mm':margin+.002,'maximum_body_local_mm':[w,h],'basis':'completepackagebody+everyCu pad,Euclideanoffset;explicitdenseassembly'})
 assert tracks(b)==oldtracks,'Coppertrack/viachanged'
 for f in b.GetFootprints():
  if f.GetReference() not in ['C9','C18','C24']:assert oldposes[f.GetReference()]==position(f),f.GetReference()
 k.SaveBoard(args.output,b)
 dest=Path(args.output).parent/'HoloCubic_RevB.pretty';dest.mkdir(exist_ok=True)
 for f in b.GetFootprints():
  cp=k.Cast_to_FOOTPRINT(f.Duplicate(False))
  if cp.GetLayer()==k.B_Cu:cp.Flip(cp.GetPosition(),False)
  cp.SetOrientationDegrees(0);cp.SetPosition(V(0,0))
  for p in cp.Pads():p.SetNetCode(0)
  k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP).FootprintSave(str(dest),cp)
 Path(args.report).write_text(json.dumps({'status':'EVALUATION_ONLY_REQUIRES_NATIVE_DRC_AND_ASSEMBLY_QUALIFICATION','source_tracks_vias_preserved':True,'pose_changes_mm':{'C9':[151.2,108.02],'C24':[158.92,99.18],'C18':[153.37,99.85]},'C18_lands':{'reference':'MurataGRM155R71C104KA88-01Ap27Table2','pad_mm':[.4,.5],'centers_local_mm':[-.4,.4],'source':'https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM155R71C104KA88-01A.pdf'},'courtyards':rebuilt},indent=2)+'\n')
 print('Assemblyenvelopesupdated;alltracks/viasunchanged')
if __name__=='__main__':main()
