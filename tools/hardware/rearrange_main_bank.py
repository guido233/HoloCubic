#!/usr/bin/env python3
"""Evaluation-copy: open two rows for NaiveRevB B0402 fanout.
Removes the olddensebank's low-currentbus, transfers the existing0.6mmFFCfeed
fromBtoL3 withoutchangingendpoints, and relocatesonly17 reviewedBresistors.
RF/MCUthermal/othercopper/poses are preserved. NativeDRCrequired.
"""
import argparse,json
from pathlib import Path
import pcbnew as k
mm=k.FromMM
V=lambda x,y:k.VECTOR2I(mm(x),mm(y))
ROWS=[['R4','R5','R12','R7','R8','R9','R10','R19','R20'],['R1','R13','R18','R16','R17','R14','R15','R11']]
def pt(p):return (round(k.ToMM(p.x),6),round(k.ToMM(p.y),6))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');ap.add_argument('--report',required=True);a=ap.parse_args();b=k.LoadBoard(a.input);assert b.GetCopperLayerCount()==4;removed=[];moved=[]
 olds=[((148.,99.8),(148.,97.25)),((148.,97.25),(142.,97.25)),((142.,97.25),(142.,103.4663)),((142.,103.4663),(141.,103.4663))]
 for t in list(b.GetTracks()):
  if isinstance(t,k.PCB_VIA):
   if t.GetNetname()=='USB_CC1' and pt(t.GetPosition())==(148.6,96.2):removed.append(t);b.Remove(t)
   continue
  if t.GetNetname()=='3V3' and t.GetLayer()==k.B_Cu and t.GetWidth()==mm(.1016):removed.append(t);b.Remove(t)
  elif t.GetNetname()=='USB_CC1' and t.GetLayer()==k.B_Cu and {pt(t.GetStart()),pt(t.GetEnd())}=={(148.6,96.2),(149.49,96.2)}:removed.append(t);b.Remove(t)
  elif t.GetNetname()=='3V3' and t.GetLayer()==k.B_Cu and any({pt(t.GetStart()),pt(t.GetEnd())}=={x,y} for x,y in olds):t.SetLayer(k.In2_Cu);moved.append(t.m_Uuid.AsString())
 assert len(moved)==4,moved
 poses={}
 for row,refs in enumerate(ROWS):
  for col,ref in enumerate(refs):
   f=b.FindFootprintByReference(ref);assert f.GetLayer()==k.B_Cu
   x,y=141.7+2*col,94.8+2.4*row;f.SetPosition(V(x,y));f.SetOrientationDegrees(0);poses[ref]=[round(x,3),round(y,3),0,'B.Cu']
 k.SaveBoard(a.output,b)
 Path(a.report).write_text(json.dumps({'status':'EVALUATION_ONLY_PENDING_NATIVE_DRC','poses':poses,'removed_obsolete_bank_tracks_and_vias':len(removed),'FFC0.6mmfeed_transferred_B_to_L3_segments':moved,'notes':['Eightcommon3V3pullupsoccupyCPprojectioncolumns;two-netandcontrolresistorsoutside','NochangeRF7/MCU21thermalvias/16paste','Original17bankbusandobsoleteR12escapeviadeleted;rootPoweragentwillfinishnewlowcurrentbus']},indent=2)+'\n')
 print('17Bresistorsplacedintworows;FFCmainfeednowL3')
if __name__=='__main__':main()
