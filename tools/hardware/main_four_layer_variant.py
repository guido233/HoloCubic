#!/usr/bin/env python3
"""Build an evaluation-only4-layer COPY; never edits the2-layer source.

Candidate dielectric uses JLCPCB public1.0mm JLC3313 table (not a released fab
stack): outer35um/PP99.4um/inner15.2um/core700um/inner15.2um/PP99.4um/outer35um.
The vendor's core-with-copper table fields are ambiguous: confirm the ordered
stack and finished tolerance before procurement. Two10um mask layers give the
bookkeeping model1.0192mm, not a guaranteed delivered finished thickness.
"""
import argparse,json,re,hashlib
from pathlib import Path
import pcbnew as k
mm=k.FromMM
V=lambda x,y:k.VECTOR2I(mm(x),mm(y))

def replace_form(text,marker,new):
 start=text.index(marker);depth=0;quoted=False;escape=False
 for i in range(start,len(text)):
  c=text[i]
  if quoted:
   if escape:escape=False
   elif c=='\\':escape=True
   elif c=='"':quoted=False
  elif c=='"':quoted=True
  elif c=='(':depth+=1
  elif c==')':
   depth-=1
   if depth==0:return text[:start]+new+text[i+1:]
 raise ValueError('Unclosedform '+marker)

def point(p):return (p.x,p.y)
def copper_signature(b):
 tracks=[]
 for t in b.GetTracks():
  via=isinstance(t,k.PCB_VIA);arc=isinstance(t,k.PCB_ARC)
  tracks.append((t.m_Uuid.AsString(),t.GetNetname(),t.GetLayer(),point(t.GetStart()),point(t.GetEnd()),point(t.GetMid()) if arc else None,t.GetWidth(k.F_Cu) if via else t.GetWidth(),t.IsLocked(),(t.GetDrillValue(),t.TopLayer(),t.BottomLayer(),t.GetViaType(),t.GetFrontTentingMode(),t.GetBackTentingMode()) if via else None))
 pads=[];poses=[]
 for f in b.GetFootprints():
  poses.append((f.GetReference(),f.m_Uuid.AsString(),point(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer(),f.GetFPID().GetUniStringLibId()))
  for p in f.Pads():
   pads.append((f.GetReference(),p.m_Uuid.AsString(),p.GetNumber(),p.GetNetname(),point(p.GetPosition()),point(p.GetSize()),point(p.GetDrillSize()),p.GetOrientationDegrees(),p.GetShape(),p.GetAttribute(),p.GetLayerSet().FmtHex(),p.GetRoundRectRadiusRatio(),p.GetChamferRectRatio(),p.GetChamferPositions(),p.GetLocalSolderMaskMargin(),p.GetLocalSolderPasteMargin(),p.GetLocalSolderPasteMarginRatio()))
 return sorted(tracks),sorted(pads),sorted(poses)
def zone_signature(z):
 p=z.Outline();contours=[]
 for i in range(p.OutlineCount()):
  q=p.COutline(i);contours.append(tuple(point(q.CPoint(n)) for n in range(q.PointCount())))
  for j in range(p.HoleCount(i)):
   q=p.CHole(i,j);contours.append(tuple(point(q.CPoint(n)) for n in range(q.PointCount())))
 return (z.GetLayerSet().FmtHex(),z.GetNetname(),z.GetAssignedPriority(),z.GetIsRuleArea(),z.GetDoNotAllowTracks(),z.GetDoNotAllowVias(),z.GetDoNotAllowPads(),z.GetDoNotAllowZoneFills(),tuple(contours))
def thermal_signature(b):
 u=b.FindFootprintByReference('U4');x,y=u.GetPosition().x,u.GetPosition().y
 vias=sorted((point(v.GetPosition()),v.GetWidth(k.F_Cu),v.GetDrillValue(),v.GetFrontTentingMode(),v.GetBackTentingMode()) for v in b.GetTracks() if isinstance(v,k.PCB_VIA) and v.GetNetname()=='GND' and abs(v.GetPosition().x-x)<mm(2.25) and abs(v.GetPosition().y-y)<mm(2.25))
 paste=sorted((point(p.GetPosition()),point(p.GetSize())) for p in u.Pads() if p.GetNumber()=='' and p.IsOnLayer(k.F_Paste) and not p.IsOnLayer(k.F_Cu))
 assert len(vias)==21 and len(paste)==16,(len(vias),len(paste))
 return vias,paste

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');args=ap.parse_args()
 assert Path(args.input).resolve()!=Path(args.output).resolve(),'Evaluationvariantmustnotreplacesource'
 source_sha=hashlib.sha256(Path(args.input).read_bytes()).hexdigest();b=k.LoadBoard(args.input);assert b.GetCopperLayerCount()==2
 all_before=copper_signature(b);thermal_before=thermal_signature(b);zones_before={z.m_Uuid.AsString():zone_signature(z) for z in b.Zones()}
 def rf_signature():
  return sorted((t.m_Uuid.AsString(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,(point(t.GetMid()) if isinstance(t,k.PCB_ARC) else None),t.GetWidth(),t.GetLayer(),t.IsLocked()) for t in b.GetTracks() if t.GetNetname()=='NetA1_1')
 before=rf_signature();b.SetCopperLayerCount(4);b.GetDesignSettings().SetBoardThickness(mm(1.0192))
 n3=next(n for n in b.GetNetsByName().values() if n.GetNetname()=='3V3');ground=next(n for n in b.GetNetsByName().values() if n.GetNetname()=='GND')
 originals=list(b.Zones());removed=[]
 # Preserve theoriginalF/Bzones. NewinnerGNDand3V3planes followtheboardoutline.
 for layer,n in [(k.In1_Cu,ground),(k.In2_Cu,n3)]:
  src=next(z for z in originals if not z.GetIsRuleArea() and z.GetLayer()==k.B_Cu and z.GetNetname()=='GND')
  z=k.Cast_to_ZONE(src.Duplicate(False));z.SetUuid(k.KIID());z.SetLayer(layer);z.SetNet(n);z.SetAssignedPriority(0);b.Add(z)
 # Originalantenna-coppervoid appliesstrictly toallcopperonnewinnerlayers.
 # OuterRFpour-onlyrule remainsunchanged so the7originalFfeedsegments staylegal.
 for src in originals:
  if not src.GetIsRuleArea():continue
  bb=src.GetBoundingBox()
  if src.GetDoNotAllowZoneFills() and not src.GetDoNotAllowTracks() and mm(7)<bb.GetWidth()<mm(8):
   z=k.Cast_to_ZONE(src.Duplicate(False));z.SetUuid(k.KIID());ls=k.LSET();ls.AddLayer(k.In1_Cu);ls.AddLayer(k.In2_Cu);z.SetLayerSet(ls);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(False);b.Add(z)
 # Alsoexcludeinnercopperbeneathall7RFfeedsegments,with0.5mmfringemargin.
 # Thisavoidssilentlyputtinga0.1mm-referenceplanebelowthehistoricfeedgeometry.
 z=k.ZONE(b);z.SetIsRuleArea(True);ls=k.LSET();ls.AddLayer(k.In1_Cu);ls.AddLayer(k.In2_Cu);z.SetLayerSet(ls);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowFootprints(False)
 p=z.Outline();p.NewOutline()
 for x,y in [(145.56,114.85),(149.7,114.85),(149.7,116.82),(145.56,116.82)]:p.Append(mm(x),mm(y))
 b.Add(z);assert before==rf_signature();assert all_before==copper_signature(b);assert thermal_before==thermal_signature(b)
 assert zones_before=={z.m_Uuid.AsString():zone_signature(z) for z in b.Zones() if z.m_Uuid.AsString() in zones_before}
 k.SaveBoard(args.output,b)
 layers=[('F.SilkS','Top Silk Screen',None),('F.Paste','Top Solder Paste',None),('F.Mask','Top Solder Mask',.01),('F.Cu','copper',.035),('dielectric 1','prepreg',.0994),('In1.Cu','copper',.0152),('dielectric 2','core',.7),('In2.Cu','copper',.0152),('dielectric 3','prepreg',.0994),('B.Cu','copper',.035),('B.Mask','Bottom Solder Mask',.01),('B.Paste','Bottom Solder Paste',None),('B.SilkS','Bottom Silk Screen',None)]
 out=['(stackup']
 for name,kind,t in layers:
  s='(layer "'+name+'" (type "'+kind+'")'
  if t is not None:s+=' (thickness '+str(t)+')'
  if kind in ['core','prepreg']:s+=' (material "'+('JLC3313 candidate - confirm ordered stack' if kind=='prepreg' else 'FR4 candidate core - confirm vendor thickness interpretation')+'") (epsilon_r '+('4.05' if kind=='prepreg' else '4.6')+') (loss_tangent 0.02)'
  out.append(s+')')
 out += ['(copper_finish "None")','(dielectric_constraints yes)',')']
 path=Path(args.output);path.write_text(replace_form(path.read_text(),'(stackup','\n'.join(out)))
 check=k.LoadBoard(args.output);assert check.GetCopperLayerCount()==4
 assert all_before==copper_signature(check);assert thermal_before==thermal_signature(check)
 assert source_sha==hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),'Sourcefilechanged'
 assert k.LoadBoard(args.input).GetCopperLayerCount()==2
 assert len([t for t in check.GetTracks() if t.GetNetname()=='NetA1_1'])==7
 report={'status':'EVALUATION_ONLY_NOT_MANUFACTURING_RELEASE','layers':['Fsignals','L2GND','L3powerandslowsignals','Bsignals'],'nominal_bookkeeping_mm':1.0192,'stack_source':'https://cart.jlcpcb.com/client/template/placeOrder/impedance.html','source_RF_segments_preserved':7,'RF_arc_midpoints_preserved':True,'all_source_tracks_vias_pads_poses_preserved':True,'source_thermal_vias_preserved':21,'source_stencil_windows_preserved':16,'source_file_sha256':source_sha,'inner_RF_rules':'originalantennaarea+all7feedsegments0.5mmmargin,nopads/tracks/vias/pour','notes':['Orderedstackandfinishedthicknesstolerancemustbeconfirmedbyfabricator','OriginalF/Bgeometryandallposespreserved','NoimpedanceorRFperformanceclaim;VNA/enclosurequalificationrequired']}
 path.with_suffix('.variant.json').write_text(json.dumps(report,indent=2)+'\n');print('Wroteevaluation-only4layercopy',path)
if __name__=='__main__':main()
