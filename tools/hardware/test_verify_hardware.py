#!/usr/bin/env python3
"""Mutation regressions against a fresh real KiCad netlist, not mock circuits.

A wiring fault is injected into the exported design in memory. Each regression
requires the corresponding independent safety assertion to reject that fault.
No design file is modified and these tests do not simulate physical hardware.
"""
import copy, os, subprocess, tempfile, unittest
from pathlib import Path
from verify_hardware import (ROOT, DEFAULT_CLI, Checks, schematic_netlist,
                             main_electrical, extend_electrical, pcb_circuit, mpu_geometry,
                             pico_geometry, stack_geometry)

class SafetyMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='holocubic-negative-test-')
        folder=ROOT/'1.Hardware/RevB-KiCad/Naive/MainBoard'
        xml=Path(cls.temp.name)/'actual.xml'
        subprocess.run([str(DEFAULT_CLI),'sch','export','netlist','--format','kicadxml','--output',str(xml),str(folder/'MainBoard.kicad_sch')],check=True,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        cls.original=schematic_netlist(xml)
        exml=Path(cls.temp.name)/'display.xml'
        subprocess.run([str(DEFAULT_CLI),'sch','export','netlist','--format','kicadxml','--output',str(exml),str(folder.parent/'ExtendBoard/ExtendBoard.kicad_sch')],check=True,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        cls.extoriginal=schematic_netlist(exml)
        _,cls.pcb,cls.fps=pcb_circuit(folder/'MainBoard.kicad_pcb')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.d=copy.deepcopy(self.original)
    def rewire(self,node,net):
        old=self.d.pins[node];self.d.groups[old].remove(node)
        self.d.pins[node]=net;self.d.groups[net].add(node)
    def bridge(self,a,b):
        target=self.d.net(*a)
        for node in list(self.d.nodes(*b)):self.rewire(node,target)
    def rejected(self,name):
        c=Checks();main_electrical(c,self.d)
        result=next(r for r in c.rows if r['check']==name)
        self.assertFalse(result['passed'],result)
    def test_baseline_satisfies_electrical_invariants(self):
        c=Checks();main_electrical(c,self.d)
        self.assertEqual([], [r for r in c.rows if not r['passed']])
    def test_cc_short_is_rejected(self):
        self.bridge(('USB1','A5'),('USB1','B5'))
        self.rejected('CC1/CC2/raw VBUS independent')
    def test_slow_legacy_ct_capacitor_is_rejected(self):
        self.d.values['C16']='1nF'
        self.rejected('C16 value')
    def test_ct_wrong_dielectric_mpn_is_rejected(self):
        self.d.mpns['C16']='injected-wrong-capacitor'
        self.rejected('Load switch CT exact C0G MPN')
    def test_missing_second_esd_ground_is_rejected(self):
        self.rewire(('U7','8'),'injected-esd-ground-open')
        self.rejected('Both TPD4E05U06 ground terminals connected')
    def test_internal_cp_regulator_tied_to_buck_is_rejected(self):
        self.bridge(('U1','6'),('U2','6'))
        self.rejected('CP internal VDD / external 3V3 / system 5V distinct')
    def test_ahct_bypass_is_rejected(self):
        self.bridge(('U4','16'),('D1','4'))
        self.rejected('RGB GPIO / buffer output / lamp DIN separate')
    def test_unused_sd_dat1_floating_is_rejected(self):
        self.rewire(('R16','2'),'injected-floating')
        self.rejected('SD pin 8 pull-up')
    def test_sd_on_gpio12_flash_voltage_strap_is_rejected(self):
        self.rewire(('U4','18'),self.d.net('J1','7'))
        self.rejected('GPIO12 flash-voltage strap remains unused')
    def test_uart_tx_routed_to_tx_is_rejected(self):
        self.rewire(('R3','1'),self.d.net('U4','41'))
        self.rejected('UART series resistor to MCU RX')
    def test_antenna_mechanical_terminal_grounded_is_rejected(self):
        self.bridge(('U4','0'),('A1','2'))
        self.rejected('CA-C03 mechanical terminal is a single unused node')
    def test_sw_and_sense_swapped_is_rejected(self):
        a=self.d.net('U2','6');b=self.d.net('U2','7')
        self.rewire(('U2','6'),b);self.rewire(('U2','7'),a)
        self.rejected('Buck VOS senses output after L1')
    def test_dvi_delay_bypass_is_rejected(self):
        self.bridge(('U5','5'),('U5','1'))
        self.rejected('BH DVI isolated from VCC by R11')
    def ext_rejected(self,name):
        c=Checks();extend_electrical(c,self.d)
        self.assertFalse(next(r for r in c.rows if r['check']==name)['passed'])
    def test_display_baseline_satisfies_electrical_invariants(self):
        c=Checks();extend_electrical(c,self.extoriginal,self.original)
        self.assertEqual([], [r for r in c.rows if not r['passed']])
    def test_display_led_cathode_ground_short_is_rejected(self):
        self.d=copy.deepcopy(self.extoriginal)
        self.bridge(('LCD1','2'),('CON1','3'))
        self.ext_rejected('Panel cathode / anode / GND separate')
    def test_display_sense_resistor_bypass_is_rejected(self):
        self.d=copy.deepcopy(self.extoriginal)
        self.bridge(('U1','5'),('U1','4'))
        self.ext_rejected('Backlight sense / cathode / GND / BIAS separate')
    def test_display_5v_to_3v3_short_is_rejected(self):
        self.d=copy.deepcopy(self.extoriginal)
        self.bridge(('CON1','1'),('CON1','2'))
        self.ext_rejected('Display 5V / 3V3 / GND separated')
    def test_display_nmos_bypass_is_rejected(self):
        self.d=copy.deepcopy(self.extoriginal)
        self.bridge(('CON1','8'),('U1','3'))
        self.ext_rejected('GPIO / NMOS gate / EN / GND / 3V3 separate')
    def test_gpio5_strap_loading_bipolar_substitute_is_rejected(self):
        # A pin-compatible BJT would load GPIO5's weak reset pull-up even
        # though ERC and the node partitions still look correct.
        self.d=copy.deepcopy(self.extoriginal)
        self.d.values['Q1']='MMBT3904'
        self.ext_rejected('Q1 value')
    def test_forbidden_mpu_center_pad_is_rejected(self):
        fps=copy.deepcopy(self.fps);fp=fps['U3']
        pad=copy.deepcopy(next(p for p in fp if isinstance(p,list) and p and p[0]=='pad'))
        pad[1]=''
        from revise_schematic import get
        get(pad,'at')[1:]=['0','0'];get(pad,'size')[1:]=['2.7','2.8'];fp.append(pad)
        c=Checks();mpu_geometry(c,self.pcb,fps)
        self.assertFalse(next(r for r in c.rows if r['check']=='MPU only pins 1–24; no unnamed/25 center pad')['passed'])
    def test_absent_mpu_keepout_is_rejected(self):
        pcb=[n for n in self.pcb if not(isinstance(n,list) and n and n[0]=='zone')]
        c=Checks();mpu_geometry(c,pcb,self.fps)
        self.assertFalse(next(r for r in c.rows if r['check']=='MPU die window covered by copper/track/via/pad keepout')['passed'])
    def test_pico_full_area_paste_is_rejected(self):
        from revise_schematic import get, alln
        fps=copy.deepcopy(self.fps)
        ep=next(p for p in alln(fps['U4'],'pad') if p[1]=='0')
        get(ep,'layers').append('F.Paste')
        c=Checks();pico_geometry(c,self.pcb,fps)
        self.assertFalse(next(r for r in c.rows if r['check']=='PICO EP has no full-area paste aperture')['passed'])
    def test_missing_pico_thermal_vias_is_rejected(self):
        pcb=[n for n in self.pcb if not(isinstance(n,list) and n and n[0]=='via')]
        c=Checks();pico_geometry(c,pcb,self.fps)
        self.assertFalse(next(r for r in c.rows if r['check']=='PICO twenty-one 0.25mm ground thermal vias / >=0.10mm annulus')['passed'])
    def test_signal_cutting_dedicated_l2_is_rejected(self):
        from revise_schematic import get, alln
        pcb=copy.deepcopy(self.pcb)
        if not any(isinstance(n,list) and n[1]=='In1.Cu' for n in get(pcb,'layers')[1:]):
            self.skipTest('two-layer engineering source has no dedicated L2')
        track=next(t for t in alln(pcb,'segment') if get(t,'net')[-1]!='GND')
        get(track,'layer')[1]='In1.Cu'
        c=Checks();stack_geometry(c,pcb)
        self.assertFalse(next(r for r in c.rows if r['check']=='Dedicated L2 ground plane has no foreign tracks or pours')['passed'])
    def test_inconsistent_finished_thickness_is_rejected(self):
        from revise_schematic import get
        pcb=copy.deepcopy(self.pcb)
        if not any(isinstance(n,list) and n[1]=='In1.Cu' for n in get(pcb,'layers')[1:]):
            self.skipTest('two-layer engineering source has no revised stack')
        thickness=get(get(pcb,'general'),'thickness');thickness[1]=str(float(thickness[1])+.1)
        c=Checks();stack_geometry(c,pcb)
        self.assertFalse(next(r for r in c.rows if r['check']=='Nominal stack thickness agrees with all copper/dielectric/mask layers')['passed'])
    def test_signal_cutting_dedicated_l5_is_rejected(self):
        from revise_schematic import get, alln
        pcb=copy.deepcopy(self.pcb)
        if not any(isinstance(n,list) and n[1]=='In4.Cu' for n in get(pcb,'layers')[1:]):
            self.skipTest('this source has no dedicated L5')
        track=next(t for t in alln(pcb,'segment') if get(t,'net')[-1]!='GND')
        get(track,'layer')[1]='In4.Cu'
        c=Checks();stack_geometry(c,pcb)
        self.assertFalse(next(r for r in c.rows if r['check']=='Dedicated L5 ground plane has no foreign tracks or pours')['passed'])

if __name__=='__main__':unittest.main()
