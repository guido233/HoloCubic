#!/usr/bin/env python3
"""Explicit DP/CC routing delta for the frozen two-row4-layer MainRevB COPY.

Only changes theUSB nets. Replaces the oldDM ESD escape loop soDP has alegal
non-via-in-pad escape; originalCP-to-USB DM B backbone/USBvias remainexact.
AllRF,thermalvias,pads/posesandPowercopper preserved. Never usesL2 forsignals.
--apply-delta merges the reviewed additions/deletions into aPowerworkcopy.
"""
import argparse,json
from pathlib import Path
import pcbnew as k
mm=k.FromMM
V=lambda p:k.VECTOR2I(mm(p[0]),mm(p[1]))
def point(p):return [round(k.ToMM(p.x),6),round(k.ToMM(p.y),6)]
def record(t):
 via=isinstance(t,k.PCB_VIA)
 d={'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'kind':'via' if via else 'track','layer':t.GetLayer(),'start':point(t.GetStart()),'end':point(t.GetEnd()),'width':k.ToMM(t.GetWidth(k.F_Cu) if via else t.GetWidth()),'locked':t.IsLocked()}
 if via:d['drill']=k.ToMM(t.GetDrillValue())
 return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');ap.add_argument('--delta');ap.add_argument('--apply-delta');a=ap.parse_args();assert Path(a.input).resolve()!=Path(a.output).resolve();b=k.LoadBoard(a.input);assert b.GetCopperLayerCount()==4
 for ref,num,n,loc in [('U1','4','USB-PWR-DP',[151.9047,98.8822]),('U7','1','USB-PWR-DP',[151.4,101.545]),('U7','2','USB-PWR-DM',[151.9,101.545]),('USB1','A6','USB-PWR-DP',[156.38617,105.2409]),('USB1','B6','USB-PWR-DP',[156.38617,104.2409]),('R12','1','USB_CC1',[145.19,94.8]),('R13','1','USB_CC2',[143.19,97.2])]:
  p=next(p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber()==num);assert p.GetNetname()==n and point(p.GetPosition())==loc,(ref,num,'Unexpectedsourcepad')
 poses=sorted((f.GetReference(),point(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()) for f in b.GetFootprints());allold={t.m_Uuid.AsString():record(t) for t in b.GetTracks()};removed=[]
 if a.apply_delta:d=json.loads(Path(a.apply_delta).read_text())
 else:
  d={'status':'EVALUATION_ONLY_REQUIRE_NATIVE_DRC','remove':[],'add':[],'notes':['OnlyoldDMESD Floop/viaandobsoleteCC1escapearedeleted','DMCP-USB BbackboneandUSBviasunchanged','DP/DM/In2 north/eastofMPUdiekeepout;L2signalsneverused','Allpackageposes,padcopper,7RFsegmentsand21thermalviaspreserved']}
  for t in b.GetTracks():
   r=record(t)
   if t.GetNetname()=='USB_CC1':d['remove'].append(r)
   elif t.GetNetname()=='USB-PWR-DM' and ((r['kind']=='via' and r['start']==[150.5,101.15]) or (r['kind']=='track' and r['layer']==k.F_Cu and all(100.9<=p[1]<=102.1 for p in [r['start'],r['end']]) and max(r['start'][0],r['end'][0])<=151.91)):d['remove'].append(r)
  def tr(n,pts,w=.15,l=k.In2_Cu):
   for p,q in zip(pts,pts[1:]):d['add'].append({'kind':'track','net':n,'layer':l,'start':p,'end':q,'width':w,'locked':True})
  def via(n,p):d['add'].append({'kind':'via','net':n,'layer':k.F_Cu,'start':p,'end':p,'width':.46,'drill':.25,'locked':True})
  # DM is keptconnectedCPtoUSB; replaceonlytheESD localbranch.
  via('USB-PWR-DM',[150.5,100.7]);tr('USB-PWR-DM',[[150.5,101.15],[150.5,100.7]],l=k.B_Cu)
  via('USB-PWR-DM',[152.0,102.1]);tr('USB-PWR-DM',[[151.9,101.545],[151.9,101.9],[152.0,102.1]],.1016,k.F_Cu)
  tr('USB-PWR-DM',[[150.5,100.7],[150.3,100.9],[150.3,102.25],[152.0,102.25],[152.0,102.1]])
  # DP CPpad4,ESDpad1,bothUSBcontacts. NoUSBtracesundertheMPUdie.
  via('USB-PWR-DP',[151.2,99.9]);tr('USB-PWR-DP',[[151.9047,98.8822],[151.9047,99.38],[151.2,99.9]],.1016,k.F_Cu)
  via('USB-PWR-DP',[150.8,101.75]);tr('USB-PWR-DP',[[151.4,101.545],[150.8,101.75]],.15,k.F_Cu)
  tr('USB-PWR-DP',[[151.2,99.9],[151.2,100.8],[150.8,101.2],[150.8,101.75]])
  tr('USB-PWR-DP',[[150.8,101.2],[150.8,101.12],[154.8,101.12],[154.8,105.2409]])
  via('USB-PWR-DP',[157.2,104.3]);tr('USB-PWR-DP',[[156.38617,104.2409],[157.2,104.2409],[157.2,104.3]],.15,k.F_Cu);tr('USB-PWR-DP',[[157.2,104.3],[157.2,104.2],[154.8,104.2]])
  via('USB-PWR-DP',[154.8,105.2409]);tr('USB-PWR-DP',[[156.38617,105.2409],[154.8,105.2409]],.15,k.F_Cu)
  # CC1 shortFescapes;resistivelegIn2,USBlegIn2outsideMPUdie.
  via('USB_CC1',[145.6,95.9]);tr('USB_CC1',[[145.19,94.8],[145.6,95.21],[145.6,95.9]],.15,k.B_Cu)
  via('USB_CC1',[152.9,102.2]);tr('USB_CC1',[[152.9,101.545],[152.9,102.2]],.15,k.F_Cu)
  tr('USB_CC1',[[145.6,95.9],[145.6,95.3],[148.82,95.3],[148.82,100.2],[149.95,100.2],[149.95,102.6],[152.9,102.6],[152.9,102.2]],.127)
  via('USB_CC1',[155.5,106.3]);tr('USB_CC1',[[156.38617,106.2409],[155.5,106.2409],[155.5,106.3]],.15,k.F_Cu)
  tr('USB_CC1',[[155.5,106.3],[154.3,106.3],[154.3,101.6],[152.9,101.6],[152.9,102.2]])
  # CC2routearound thePowerbus andnorthofdie. LocalF .1016mmneckfits
  # the0.36mmactualgapbetweenC20andD2with >=0.127mmeachside.
  via('USB_CC2',[143.5,98.55]);tr('USB_CC2',[[143.19,97.2],[143.5,97.51],[143.5,98.55]],.15,k.B_Cu)
  via('USB_CC2',[153.85,102.1]);tr('USB_CC2',[[153.4,101.545],[153.4,101.85],[153.85,102.1]],.1016,k.F_Cu)
  tr('USB_CC2',[[156.38617,103.2409],[155.5,103.2409],[155.5,102.34],[153.85,102.34],[153.85,102.1]],.1016,k.F_Cu)
  tr('USB_CC2',[[143.5,98.55],[147.2,98.55],[147.2,100.6],[148.95,100.6],[148.95,102.9],[153.4,102.9],[153.4,102.5],[153.85,102.5],[153.85,102.1]])
 ids={t.m_Uuid.AsString():t for t in b.GetTracks()}
 for r in d['remove']:
  t=ids.get(r['uuid']);assert t is not None,'Missingreviewedsourceitem '+r['uuid'];assert record(t)==r,'Sourcegeometrychanged '+r['uuid'];removed.append(t);b.Remove(t)
 nets={n.GetNetname():n for n in b.GetNetsByName().values()}
 for r in d['add']:
  if r['kind']=='via':
   t=k.PCB_VIA(b);t.SetPosition(V(r['start']));t.SetWidth(mm(r['width']));t.SetDrill(mm(r['drill']));t.SetLayerPair(k.F_Cu,k.B_Cu);t.SetFrontTentingMode(k.TENTING_MODE_TENTED);t.SetBackTentingMode(k.TENTING_MODE_TENTED)
  else:
   assert r['layer']!=k.In1_Cu,'SignalontheGNDlayer';t=k.PCB_TRACK(b);t.SetStart(V(r['start']));t.SetEnd(V(r['end']));t.SetWidth(mm(r['width']));t.SetLayer(r['layer'])
  t.SetNet(nets[r['net']]);t.SetLocked(True);b.Add(t)
 assert poses==sorted((f.GetReference(),point(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()) for f in b.GetFootprints())
 after={t.m_Uuid.AsString():record(t) for t in b.GetTracks()};gone={r['uuid'] for r in d['remove']}
 assert all(after[u]==r for u,r in allold.items() if u not in gone),'Unrelatedsourcecopperchanged'
 b.BuildConnectivity();k.SaveBoard(a.output,b)
 if a.delta:Path(a.delta).write_text(json.dumps(d,indent=2)+'\n')
 print('USBdelta applied:',len(d['remove']),'removed;',len(d['add']),'added;allothercopper/posespreserved')
if __name__=='__main__':main()
