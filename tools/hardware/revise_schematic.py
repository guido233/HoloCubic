#!/usr/bin/env python3
"""Rebuild a native imported Naive schematic from its pins and a RevB manifest.

Uses only Python's standard library. Preserve a pristine native import and pass
it with --source; the original Altium project is always kept as the reference.
Electrical changes come from revb_main_manifest.json. Never edits a PCB/project.
"""
import argparse, copy, json, math, re, uuid
from pathlib import Path
import xml.etree.ElementTree as ET

class Q(str): pass

def parse(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text)
    stack=[]; root=None
    for t in tokens:
        if t=='(':
            n=[]
            if stack: stack[-1].append(n)
            else: root=n
            stack.append(n)
        elif t==')': stack.pop()
        else: stack[-1].append(Q(json.loads(t)) if t.startswith('"') else t)
    return root

def dump(n, level=0):
    if isinstance(n,Q): return json.dumps(str(n),ensure_ascii=False)
    if not isinstance(n,list): return str(n)
    if not any(isinstance(x,list) for x in n): return '('+' '.join(dump(x) for x in n)+')'
    a=[]; i=0
    while i<len(n) and not isinstance(n[i],list): a.append(dump(n[i])); i+=1
    return '('+' '.join(a)+''.join('\n'+'\t'*(level+1)+dump(x,level+1) for x in n[i:])+'\n'+'\t'*level+')'

def get(n,key,default=None): return next((x for x in n if isinstance(x,list) and x and x[0]==key),default)
def alln(n,key): return [x for x in n if isinstance(x,list) and x and x[0]==key]
def prop(n,key): return next((x for x in alln(n,'property') if x[1]==key),None)
def uid(): return Q(str(uuid.uuid4()))
def write(path,n): Path(path).write_text(dump(n)+'\n')
def annotate(source,output):
    n=parse(Path(source).read_text()); c=0
    for s in alln(n,'symbol'):
        ref=prop(s,'Reference')
        if ref[2].startswith('#PWR'):
            c+=1; ref[2]=Q('#PWR%03d'%c)
            for projects in alln(get(s,'instances',[]),'project'):
                for p in alln(projects,'path'): get(p,'reference')[1]=ref[2]
    write(output,n)
    return n

# Original Naive pin/net mapping, derived from the source PcbDoc and native
# schematic import; unconnected MCU pads remain explicitly unused.
BASE_PARTS = {'J1': {'value': 'TF-Socket',
        'footprint': 'TF-Card-Amphenol with TF',
        'uuid': '036f4eda-700d-41ff-ba17-68fad1ad7e32',
        'pins': {'1': {'name': 'DATA_LINE[BIT_2]', 'type': 'passive', 'net': None},
                 '2': {'name': 'CARD_DETECT/DATA_LINE[BIT_3]', 'type': 'passive', 'net': 'GPIO15'},
                 '3': {'name': 'COMMAND/RESPONSE', 'type': 'passive', 'net': 'GPIO13'},
                 '4': {'name': 'VCC', 'type': 'passive', 'net': '3V3'},
                 '5': {'name': 'CLOCK', 'type': 'passive', 'net': 'GPIO14'},
                 '6': {'name': 'GND', 'type': 'passive', 'net': 'GND'},
                 '7': {'name': 'DATA_LINE[BIT_0]', 'type': 'passive', 'net': 'GPIO26'},
                 '8': {'name': 'DATA_LINE[BIT_1]', 'type': 'passive', 'net': None},
                 '9': {'name': 'CD_SWITCH1', 'type': 'passive', 'net': 'GND'},
                 '10': {'name': 'CD_SWITCH2', 'type': 'passive', 'net': 'GND'},
                 'S1': {'name': 'SHIELD', 'type': 'passive', 'net': 'GND'},
                 'S2': {'name': 'SHIELD', 'type': 'passive', 'net': 'GND'},
                 'S3': {'name': 'SHIELD', 'type': 'passive', 'net': 'GND'},
                 'S4': {'name': 'SHIELD', 'type': 'passive', 'net': 'GND'}}},
 'R11': {'value': '10K',
         'footprint': 'RES_0402',
         'uuid': '1823734d-351b-4a00-9564-bf1c4eb34150',
         'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'NetR11_1'},
                  '2': {'name': '2', 'type': 'passive', 'net': '3V3'}}},
 'C11': {'value': '0.1uF',
         'footprint': 'CAP_0402',
         'uuid': '1ed7ce11-0e0d-45b8-9309-5773da619892',
         'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                  '2': {'name': '2', 'type': 'passive', 'net': 'GND'}}},
 'C5': {'value': '0.1uF',
        'footprint': 'CAP_0402',
        'uuid': '1fc21215-a9d3-409b-a74a-64a46317a591',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': '3V3A'}}},
 'C4': {'value': '10uF',
        'footprint': 'CAP_0402',
        'uuid': '20bfafb2-fd15-4a99-ae98-6112c6082643',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': '3V3A'}}},
 'R1': {'value': '10K',
        'footprint': 'RES_0402',
        'uuid': '2af07117-e95b-45e9-a41b-0b90158b38a7',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'VDD_5V'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetR1_2'}}},
 'U5': {'value': 'BH1750FVI-TR',
        'footprint': 'BH1750FVI',
        'uuid': '3aa079d3-99a1-4c47-a38c-21d2f1bcc421',
        'pins': {'1': {'name': 'VCC', 'type': 'power_in', 'net': '3V3'},
                 '2': {'name': 'ADDR', 'type': 'input', 'net': 'GND'},
                 '3': {'name': 'GND', 'type': 'power_in', 'net': 'GND'},
                 '4': {'name': 'SDA', 'type': 'bidirectional', 'net': 'BH_SDA'},
                 '5': {'name': 'DVI', 'type': 'passive', 'net': 'NetR11_1'},
                 '6': {'name': 'SCL', 'type': 'input', 'net': 'BH_SCL'}}},
 'A1': {'value': 'RAINSUN',
        'footprint': 'ANT-Rainsun-AN5120',
        'uuid': '3ec0c61c-f80b-493f-a049-eb6d63d80ae9',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'NetA1_1'}}},
 'R4': {'value': '12K',
        'footprint': 'RES_0402',
        'uuid': '480a12a3-30de-4506-819f-f5caa71d6bf5',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'DTR'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetR4_2'}}},
 'USB1': {'value': 'Type-C',
          'footprint': 'Type-C-TOP',
          'uuid': '4925330a-785f-4fd4-b977-3323c5f7154d',
          'pins': {'1': {'name': 'SH1', 'type': 'passive', 'net': 'GND'},
                   '2': {'name': 'SH2', 'type': 'passive', 'net': 'GND'},
                   '3': {'name': 'SH3', 'type': 'passive', 'net': 'GND'},
                   '4': {'name': 'SH4', 'type': 'passive', 'net': 'GND'},
                   'A1': {'name': 'GND', 'type': 'passive', 'net': 'GND'},
                   'A2': {'name': 'TX1+', 'type': 'passive', 'net': None},
                   'A3': {'name': 'TX1-', 'type': 'passive', 'net': None},
                   'A4': {'name': 'VBUS', 'type': 'passive', 'net': 'VDD_5V'},
                   'A5': {'name': 'CC1', 'type': 'passive', 'net': None},
                   'A6': {'name': 'D+', 'type': 'passive', 'net': 'USB-PWR-DP'},
                   'A7': {'name': 'D-', 'type': 'passive', 'net': 'USB-PWR-DM'},
                   'A8': {'name': 'SBU1', 'type': 'passive', 'net': None},
                   'A9': {'name': 'VBUS', 'type': 'passive', 'net': 'VDD_5V'},
                   'A10': {'name': 'RX2-', 'type': 'passive', 'net': None},
                   'A11': {'name': 'RX2+', 'type': 'passive', 'net': None},
                   'A12': {'name': 'GND', 'type': 'passive', 'net': 'GND'},
                   'B1': {'name': 'GND', 'type': 'passive', 'net': 'GND'},
                   'B2': {'name': 'TX2+', 'type': 'passive', 'net': None},
                   'B3': {'name': 'TX2-', 'type': 'passive', 'net': None},
                   'B4': {'name': 'VBUS', 'type': 'passive', 'net': 'VDD_5V'},
                   'B5': {'name': 'CC2', 'type': 'passive', 'net': None},
                   'B6': {'name': 'D+', 'type': 'passive', 'net': 'USB-PWR-DP'},
                   'B7': {'name': 'D-', 'type': 'passive', 'net': 'USB-PWR-DM'},
                   'B8': {'name': 'SBU2', 'type': 'passive', 'net': None},
                   'B9': {'name': 'VBUS', 'type': 'passive', 'net': 'VDD_5V'},
                   'B10': {'name': 'RX1-', 'type': 'passive', 'net': None},
                   'B11': {'name': 'RX1+', 'type': 'passive', 'net': None},
                   'B12': {'name': 'GND', 'type': 'passive', 'net': 'GND'}}},
 'C8': {'value': '0.1uF',
        'footprint': 'CAP_0402',
        'uuid': '4a4dd8db-9432-42b1-b0e0-b745c2fdc083',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'NetC8_1'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GND'}}},
 'D1': {'value': 'WS2812B-V5/W',
        'footprint': 'LED_5050_WS2812B',
        'uuid': '4a593d67-2f01-44a9-91a2-67d35bc53fbe',
        'pins': {'1': {'name': 'VDD', 'type': 'power_in', 'net': 'VDD_5V'},
                 '2': {'name': 'DOUT', 'type': 'output', 'net': None},
                 '3': {'name': 'GND', 'type': 'power_in', 'net': 'GND'},
                 '4': {'name': 'DIN', 'type': 'input', 'net': 'GPIO27'}}},
 'R8': {'value': '10K',
        'footprint': 'RES_0402',
        'uuid': '4bc8dee3-f30c-4e77-bfd4-e8b4b71b5e3c',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GPIO13'}}},
 'C2': {'value': '10uF',
        'footprint': 'CAP_0402',
        'uuid': '4edd19f1-0a79-4163-81b8-24c11d2702e3',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': '3V3'}}},
 'R9': {'value': '10K',
        'footprint': 'RES_0402',
        'uuid': '59df2c9e-d16b-432e-aa8c-63f372a108e6',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GPIO14'}}},
 'R7': {'value': '10K',
        'footprint': 'RES_0402',
        'uuid': '5a997410-384c-4189-9b8c-871480810be4',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GPIO26'}}},
 'U1': {'value': 'CP2102',
        'footprint': 'QFN-28',
        'uuid': '6d990930-ca24-4125-89d4-8b4e6e54561f',
        'pins': {'1': {'name': 'DCD', 'type': 'input', 'net': None},
                 '2': {'name': 'RI', 'type': 'input', 'net': None},
                 '3': {'name': 'GND', 'type': 'power_in', 'net': 'GND'},
                 '4': {'name': 'D+', 'type': 'bidirectional', 'net': 'USB-PWR-DP'},
                 '5': {'name': 'D-', 'type': 'bidirectional', 'net': 'USB-PWR-DM'},
                 '6': {'name': 'VDD', 'type': 'power_out', 'net': None},
                 '7': {'name': 'REGIN', 'type': 'power_in', 'net': 'VDD_5V'},
                 '8': {'name': 'VBUS', 'type': 'input', 'net': 'VDD_5V'},
                 '9': {'name': '*RST', 'type': 'bidirectional', 'net': 'NetR1_2'},
                 '10': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '11': {'name': '*SUSPEND', 'type': 'output', 'net': None},
                 '12': {'name': 'SUSPEND', 'type': 'output', 'net': None},
                 '13': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '14': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '15': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '16': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '17': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '18': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '19': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '20': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '21': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '22': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '23': {'name': 'CTS', 'type': 'input', 'net': None},
                 '24': {'name': 'RTS', 'type': 'output', 'net': 'RTS'},
                 '25': {'name': 'RXD', 'type': 'input', 'net': 'CP_Rx'},
                 '26': {'name': 'TXD', 'type': 'output', 'net': 'NetR3_2'},
                 '27': {'name': 'DSR', 'type': 'input', 'net': None},
                 '28': {'name': 'DTR', 'type': 'output', 'net': 'DTR'},
                 '29': {'name': 'HEAT_TAB', 'type': 'power_in', 'net': 'GND'}}},
 'C3': {'value': '10nF',
        'footprint': 'CAP_0402',
        'uuid': '6dc836a3-93ec-4224-9ec6-31fe37d702f6',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetC3_2'}}},
 'R5': {'value': '12K',
        'footprint': 'RES_0402',
        'uuid': '7286ff2e-9e1b-4bae-ac24-8b4b0fb69403',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'RTS'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetR5_2'}}},
 'U2': {'value': 'LP2992 3V3',
        'footprint': 'SOT23-5',
        'uuid': '790a656c-ae3d-434b-b04e-e4fe83b7dba1',
        'pins': {'1': {'name': 'VIN', 'type': 'passive', 'net': 'VDD_5V'},
                 '2': {'name': 'GND', 'type': 'passive', 'net': 'GND'},
                 '3': {'name': 'ON/OFF', 'type': 'passive', 'net': 'VDD_5V'},
                 '4': {'name': 'BYPASS', 'type': 'passive', 'net': 'NetC3_2'},
                 '5': {'name': 'VOUT', 'type': 'passive', 'net': '3V3'}}},
 'R3': {'value': '200R',
        'footprint': 'RES_0402',
        'uuid': '7b4fecf7-ec40-466a-be5f-b7976867abfa',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'CP_Tx'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetR3_2'}}},
 'R2': {'value': '0R',
        'footprint': 'RES_0402',
        'uuid': '80a9ebbe-2a26-4ec6-81e2-7a2c4cac6312',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                 '2': {'name': '2', 'type': 'passive', 'net': '3V3A'}}},
 'VT2': {'value': 'S8050',
         'footprint': 'SMT_TRIODE_NPN',
         'uuid': '83ae2094-2acd-4f46-aec4-3455790201f2',
         'pins': {'1': {'name': 'B', 'type': 'input', 'net': 'NetR5_2'},
                  '2': {'name': 'E', 'type': 'passive', 'net': 'DTR'},
                  '3': {'name': 'C', 'type': 'open_collector', 'net': 'GPIO0'}}},
 'R6': {'value': '10K',
        'footprint': 'RES_0402',
        'uuid': '89beacb9-08aa-4d86-9ed8-5e2130c5a1e4',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3A'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'EN'}}},
 'C7': {'value': '0.1uF',
        'footprint': 'CAP_0402',
        'uuid': '8bdee3b0-930c-4d98-b41b-9bd8741add0c',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'EN'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GND'}}},
 'C6': {'value': '10nF',
        'footprint': 'CAP_0402',
        'uuid': '8e174305-f65e-4d57-9d99-a9be42968d85',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'GND'}}},
 'U3': {'value': 'MPU6050',
        'footprint': 'QFN-24',
        'uuid': '90c41636-c05d-4349-a0dc-5e9ab2b34e67',
        'pins': {'1': {'name': 'CLKIN', 'type': 'input', 'net': 'GND'},
                 '2': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '3': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '4': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '5': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '6': {'name': 'A_DA', 'type': 'bidirectional', 'net': None},
                 '7': {'name': 'A_CL', 'type': 'output', 'net': None},
                 '8': {'name': 'VLogic', 'type': 'power_in', 'net': '3V3'},
                 '9': {'name': 'AD0', 'type': 'input', 'net': 'GND'},
                 '10': {'name': 'REGOUT', 'type': 'power_out', 'net': 'NetC8_1'},
                 '11': {'name': 'FSYNC', 'type': 'input', 'net': 'GND'},
                 '12': {'name': 'INT', 'type': 'output', 'net': None},
                 '13': {'name': 'VDD', 'type': 'power_in', 'net': '3V3'},
                 '14': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '15': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '16': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '17': {'name': 'NC', 'type': 'no_connect', 'net': None},
                 '18': {'name': 'GND', 'type': 'power_in', 'net': 'GND'},
                 '19': {'name': 'RESV', 'type': 'no_connect', 'net': None},
                 '20': {'name': 'CPOUT', 'type': 'output', 'net': 'NetC9_2'},
                 '21': {'name': 'RESV', 'type': 'no_connect', 'net': None},
                 '22': {'name': 'CLKOUT', 'type': 'output', 'net': None},
                 '23': {'name': 'SCL', 'type': 'input', 'net': 'BH_SCL'},
                 '24': {'name': 'SDA', 'type': 'bidirectional', 'net': 'BH_SDA'}}},
 'R10': {'value': '10K',
         'footprint': 'RES_0402',
         'uuid': '9a86d532-7819-4493-8d96-e85e307444ba',
         'pins': {'1': {'name': '1', 'type': 'passive', 'net': '3V3'},
                  '2': {'name': '2', 'type': 'passive', 'net': 'GPIO15'}}},
 'C10': {'value': '0.1uF',
         'footprint': 'CAP_0402',
         'uuid': '9b7b0381-cbbd-4e1e-85f8-db3f8b7ed2db',
         'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                  '2': {'name': '2', 'type': 'passive', 'net': '3V3'}}},
 'CON1': {'value': 'FFC_0.5_8',
          'footprint': 'FFC_0.5_8',
          'uuid': 'b2720441-1512-49fe-ba01-9b313defc353',
          'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GPIO5'},
                   '2': {'name': '2', 'type': 'passive', 'net': 'GPIO4'},
                   '3': {'name': '3', 'type': 'passive', 'net': 'GPIO23'},
                   '4': {'name': '4', 'type': 'passive', 'net': 'GPIO18'},
                   '5': {'name': '5', 'type': 'passive', 'net': 'DC'},
                   '6': {'name': '6', 'type': 'passive', 'net': 'GND'},
                   '7': {'name': '7', 'type': 'passive', 'net': '3V3'},
                   '8': {'name': '8', 'type': 'passive', 'net': 'VDD_5V'}}},
 'C1': {'value': '0.1uF',
        'footprint': 'CAP_0402',
        'uuid': 'bb3a365d-1346-4411-a8ac-4e625f235873',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': '3V3'}}},
 'U4': {'value': 'ESP32_SIP',
        'footprint': 'QFN-48_7X7',
        'uuid': 'e166c97f-6304-473f-b21e-db07f545bf55',
        'pins': {'0': {'name': 'GND', 'type': 'power_in', 'net': 'GND'},
                 '1': {'name': 'VDDA', 'type': 'power_in', 'net': '3V3A'},
                 '2': {'name': 'LNA_IN', 'type': 'bidirectional', 'net': 'NetA1_1'},
                 '3': {'name': 'VDD3P3', 'type': 'power_in', 'net': '3V3A'},
                 '4': {'name': 'VDD3P3', 'type': 'power_in', 'net': '3V3A'},
                 '5': {'name': 'SENSOR_VP', 'type': 'input', 'net': None},
                 '6': {'name': 'SENSOR_CAPP', 'type': 'input', 'net': None},
                 '7': {'name': 'SENSOR_CAPN', 'type': 'input', 'net': None},
                 '8': {'name': 'SENSOR_VN', 'type': 'input', 'net': None},
                 '9': {'name': 'CHIP_PU', 'type': 'input', 'net': 'EN'},
                 '10': {'name': 'VDET_1', 'type': 'input', 'net': None},
                 '11': {'name': 'VDET_2', 'type': 'input', 'net': None},
                 '12': {'name': '32K_XP', 'type': 'bidirectional', 'net': 'BH_SDA'},
                 '13': {'name': '32K_XN', 'type': 'bidirectional', 'net': 'BH_SCL'},
                 '14': {'name': 'GPIO25', 'type': 'bidirectional', 'net': None},
                 '15': {'name': 'GPIO26', 'type': 'bidirectional', 'net': 'GPIO26'},
                 '16': {'name': 'GPIO27', 'type': 'bidirectional', 'net': 'GPIO27'},
                 '17': {'name': 'MTMS', 'type': 'bidirectional', 'net': 'GPIO14'},
                 '18': {'name': 'MTDI', 'type': 'bidirectional', 'net': None},
                 '19': {'name': 'VDD3P3_RTC', 'type': 'power_in', 'net': '3V3A'},
                 '20': {'name': 'MTCK', 'type': 'bidirectional', 'net': 'GPIO13'},
                 '21': {'name': 'MTDO', 'type': 'bidirectional', 'net': 'GPIO15'},
                 '22': {'name': 'GPIO2', 'type': 'bidirectional', 'net': 'DC'},
                 '23': {'name': 'GPIO0', 'type': 'bidirectional', 'net': 'GPIO0'},
                 '24': {'name': 'GPIO4', 'type': 'bidirectional', 'net': 'GPIO4'},
                 '25': {'name': 'IO16(FLASH_CS)', 'type': 'bidirectional', 'net': None},
                 '26': {'name': 'VDD_SDIO_NC', 'type': 'no_connect', 'net': None},
                 '27': {'name': 'IO17(FLASH_SD0)', 'type': 'bidirectional', 'net': None},
                 '28': {'name': 'SD_DATA_2/IO9', 'type': 'bidirectional', 'net': None},
                 '29': {'name': 'SD_DATA_3/IO10', 'type': 'bidirectional', 'net': None},
                 '30': {'name': 'SD_CMD(FLASH_SD2)', 'type': 'bidirectional', 'net': None},
                 '31': {'name': 'SD_CLK(FLASH_CLK)', 'type': 'bidirectional', 'net': None},
                 '32': {'name': 'SD_DATA_0(FLASH_SD3)', 'type': 'bidirectional', 'net': None},
                 '33': {'name': 'SD_DATA_1(FLASH_SD1)', 'type': 'bidirectional', 'net': None},
                 '34': {'name': 'GPIO5', 'type': 'bidirectional', 'net': 'GPIO5'},
                 '35': {'name': 'GPIO18', 'type': 'bidirectional', 'net': 'GPIO18'},
                 '36': {'name': 'GPIO23', 'type': 'bidirectional', 'net': 'GPIO23'},
                 '37': {'name': 'VDD3P3_CPU', 'type': 'power_in', 'net': '3V3A'},
                 '38': {'name': 'GPIO19', 'type': 'bidirectional', 'net': None},
                 '39': {'name': 'GPIO22', 'type': 'bidirectional', 'net': None},
                 '40': {'name': 'U0RXD', 'type': 'input', 'net': 'CP_Tx'},
                 '41': {'name': 'U0TXD', 'type': 'output', 'net': 'CP_Rx'},
                 '42': {'name': 'GPIO21', 'type': 'bidirectional', 'net': None},
                 '43': {'name': 'VDDA', 'type': 'power_in', 'net': '3V3A'},
                 '44': {'name': 'XTAL_N_NC', 'type': 'no_connect', 'net': None},
                 '45': {'name': 'XTAL_P_NC', 'type': 'no_connect', 'net': None},
                 '46': {'name': 'VDDA', 'type': 'power_in', 'net': '3V3A'},
                 '47': {'name': 'CAP2_NC', 'type': 'no_connect', 'net': None},
                 '48': {'name': 'CAP1_NC', 'type': 'no_connect', 'net': None}}},
 'VT1': {'value': 'S8050',
         'footprint': 'SMT_TRIODE_NPN',
         'uuid': 'f5e592b8-4b90-45df-ab61-f836742ba85e',
         'pins': {'1': {'name': 'B', 'type': 'input', 'net': 'NetR4_2'},
                  '2': {'name': 'E', 'type': 'passive', 'net': 'RTS'},
                  '3': {'name': 'C', 'type': 'open_collector', 'net': 'EN'}}},
 'C9': {'value': '2.2nF',
        'footprint': 'CAP_0402',
        'uuid': 'ff87da24-01b3-4e86-93f0-0d46cf874521',
        'pins': {'1': {'name': '1', 'type': 'passive', 'net': 'GND'},
                 '2': {'name': '2', 'type': 'passive', 'net': 'NetC9_2'}}}}

# The source SchDoc drew a 24-contact USB symbol, but PcbDoc has the
# USB2 16-contact footprint. Do not invent nonexistent SuperSpeed pads.
for unused_usb_pin in ['A2','A3','A10','A11','B2','B3','B10','B11']:
    BASE_PARTS['USB1']['pins'].pop(unused_usb_pin)
for old_usb_shell in ['1','2','3','4']:
    BASE_PARTS['USB1']['pins'].pop(old_usb_shell)
BASE_PARTS['USB1']['pins']['SH']={'name':'SHIELD','type':'passive','net':'GND'}
BASE_PARTS['USB1']['value']='USB4105-GF-A'
BASE_PARTS['USB1']['note']='GCT USB4105-GF-A; official land pattern revision; mating face and port height require mechanical registration.'

# Imported FFC symbol omitted the grounded mounting pad present in the PCB.
BASE_PARTS['CON1']['pins']['MP']={'name':'SHIELD','type':'passive','net':'GND'}

ROOT_UUID='1eb24f81-ec48-41e3-9ef9-a41f2d96ce37'
NS=uuid.UUID(ROOT_UUID)
def stable(name): return Q(str(uuid.uuid5(NS,name)))
def num(x): return ('%.4f'%x).rstrip('0').rstrip('.') or '0'
def effects(size=1.0,justify=None,hide=False):
    e=['effects',['font',['size',num(size),num(size)]]]
    if justify:e.append(['justify',*justify.split()])
    if hide:e.append(['hide','yes'])
    return e

def field(key,val,x,y,size=1.0,hide=False):
    f=['property',Q(key),Q(val),['at',num(x),num(y),'0']]
    if hide:f.append(['hide','yes'])
    f.append(effects(size)); return f

def line(points,width=0.254):
    return ['polyline',['pts',*[['xy',num(x),num(y)] for x,y in points]],['stroke',['width',num(width)],['type','default']],['fill',['type','none']]]

NEW_PINS={
'U2': [('1','PGND','power_in'),('2','VIN','power_in'),('3','EN','input'),('4','AGND','power_in'),('5','FB','input'),('6','VOS','input'),('7','SW','power_out'),('8','PG','open_collector'),('9','EP/GND','power_in')],
'U6': [('1','VIN','power_in'),('2','GND','power_in'),('3','ON','input'),('4','CT','passive'),('5','QOD','passive'),('6','VOUT','power_out')],
'U7': [('1','D1+','passive'),('2','D1-','passive'),('3','GND','power_in'),('4','D2+','passive'),('5','D2-','passive'),('6','NC','no_connect'),('7','NC','no_connect'),('8','GND','power_in'),('9','NC','no_connect'),('10','NC','no_connect')],
'U8': [('1','~{OE}','input'),('2','A','input'),('3','GND','power_in'),('4','Y','output'),('5','VCC','power_in')],
'D2': [('1','I/O','passive'),('2','GND','passive')],
'A1': [('1','RF_FEED','passive'),('2','MOUNT_NC','no_connect')],
'J1': [('1','DAT2','passive'),('2','CD/DAT3','passive'),('3','CMD','passive'),('4','VDD','power_in'),('5','CLK','passive'),('6','VSS','power_in'),('7','DAT0','passive'),('8','DAT1','passive'),('9','CD_SWITCH1','passive'),('10','CD_SWITCH2','passive'),('SH','SHIELD','passive')],
}

# A2 functional blocks, all coordinates on a 50 mil grid where practical.
POSITIONS={
'USB1':(57.15,66.04), 'U7':(157.48,66.04), 'R12':(57.15,115.57),'R13':(57.15,129.54),
'D2':(157.48,115.57),'C15':(157.48,129.54),'C22':(157.48,143.51),
'U6':(251.46,53.34),'U2':(350.52,53.34),'R18':(232.41,87.63),'C17':(312.42,87.63),'C16':(391.16,87.63),
'C1':(232.41,113.03),'C3':(232.41,127.0),'C12':(232.41,140.97),
'C2':(312.42,113.03),'C13':(312.42,127),'C14':(312.42,140.97),
'L1':(391.16,113.03),'C4':(391.16,127),'C5':(391.16,140.97),'R2':(350.52,158.75),
'U8':(458.47,53.34),'D1':(539.75,53.34),'R19':(458.47,90.17),'R20':(539.75,90.17),
'C20':(59.69,327.66),'C21':(539.75,116.84),
'U1':(59.69,234.95),'R1':(59.69,285.75),'R3':(59.69,299.72),'C18':(59.69,313.69),'C19':(59.69,327.66),'C23':(59.69,341.63),
'R4':(160.02,205.74),'VT1':(160.02,227.33),'R5':(160.02,262.89),'VT2':(160.02,284.48),
'R6':(160.02,320.04),'C7':(160.02,334.01),
'U4':(309.88,234.95),'A1':(309.88,295.91),
'U3':(457.2,214.63),'U5':(538.48,214.63),
'C24':(538.48,238.76),'C6':(457.2,251.46),'C8':(457.2,265.43),'C9':(538.48,251.46),'C10':(538.48,265.43),
'R14':(457.2,279.4),'R15':(538.48,279.4),'C11':(457.2,293.37),'R11':(538.48,293.37),
'J1':(260.35,361.95),'R7':(365.76,325.12),'R8':(365.76,339.09),'R9':(365.76,353.06),
'R10':(365.76,367.03),'R16':(365.76,381.0),'R17':(365.76,394.97),'CON1':(463.55,349.25),
}

def symbol_definition(key,pins):
    """Return self-contained library symbol and electrical pin end coordinates."""
    name=key; pts={}; k=key[0]
    lib=['symbol',Q(name),['pin_names',['offset','0.635']],['exclude_from_sim','no'],['in_bom','yes'],['on_board','yes'],
         field('Reference',key[0],0,5,1.0),field('Value',name,0,-5,1.0)]
    gfx=['symbol',Q(name+'_0_1')]; body=['symbol',Q(name+'_1_1')]
    if key in ['R','C','L','D2']:
        pts={'1':(-5.08,0,0),'2':(5.08,0,180)}
        if key=='C':
            gfx += [line([(-.762,-2.032),(-.762,2.032)]),line([(.762,-2.032),(.762,2.032)]),line([(-2.54,0),(-.762,0)]),line([(.762,0),(2.54,0)])]
        elif key=='L':
            gfx += [line([(-2.54,0),(-2.54,1.27),(-1.27,1.27),(-1.27,-1.27),(0,-1.27),(0,1.27),(1.27,1.27),(1.27,-1.27),(2.54,-1.27),(2.54,0)])]
        elif key=='D2':
            gfx += [['rectangle',['start','-2.54','1.27'],['end','2.54','-1.27'],['stroke',['width','0.254'],['type','default']],['fill',['type','background']]],line([(-1.27,1.27),(1.27,-1.27)])]
        else:
            gfx += [['rectangle',['start','-2.54','1.016'],['end','2.54','-1.016'],['stroke',['width','0.254'],['type','default']],['fill',['type','none']]]]
        for no,p in pins.items():
            x,y,a=pts[no]; body.append(pin_node(no,'~',p['type'],x,y,a,2.54,False))
        height=3.0
    elif key in ['VT1','VT2','Q1']:
        pts={'1':(-5.08,0,0),'2':(5.08,-3.81,180),'3':(5.08,3.81,180)}
        gfx += [line([(-2.54,0),(-1.27,0)]),line([(-1.27,-2.54),(-1.27,2.54)]),
                line([(-1.27,1.27),(2.54,3.81)]),line([(-1.27,-1.27),(2.54,-3.81)]),
                line([(0.762,-3.556),(2.54,-3.81),(1.778,-2.159)])]
        for no,p in pins.items():
            x,y,a=pts[no];body.append(pin_node(no,'~',p['type'],x,y,a,2.54,False))
        height=10.16
    elif key=='A1':
        pts={'1':(-5.08,0,0)}; gfx += [line([(-2.54,0),(0,0),(0,3.81),(-2.54,6.35),(2.54,6.35),(0,3.81)])]
        body.append(pin_node('1','RF','passive',-5.08,0,0,2.54,False)); height=15.24
        if '2' in pins:
            # CA-C03 has a soldered mounting terminal isolated from RF and GND.
            pts['2']=(5.08,-2.54,180)
            body.append(pin_node('2','MOUNT_NC','no_connect',5.08,-2.54,180,2.54,True))
    else:
        items=list(pins.items()); left=items[:math.ceil(len(items)/2)]; right=items[len(left):]
        width= {'U4':55.88,'U1':43.18,'U3':33.02,'USB1':35.56,'J1':43.18,'U5':30.48,'CON1':25.4}.get(key,33.02)
        half=width/2; height=max(len(left),len(right))*2.54+2.54; top=(max(len(left),len(right))-1)*1.27
        gfx.append(['rectangle',['start',num(-half),num(height/2)],['end',num(half),num(-height/2)],['stroke',['width','0.254'],['type','default']],['fill',['type','background']]])
        for side,items in [(-1,left),(1,right)]:
            for i,(no,p) in enumerate(items):
                x=side*(half+5.08); y=top-i*2.54; a=0 if side<0 else 180;pts[no]=(x,y,a)
                body.append(pin_node(no,p['name'],p['type'],x,y,a,5.08,True))
    lib += [gfx,body];return lib,pts,height

def pin_node(no,name,typ,x,y,a,length,show=True):
    p=['pin',typ,'line',['at',num(x),num(y),str(a)],['length',num(length)],['name',Q(name),effects(.85)],['number',Q(no),effects(.85)]]
    if not show:p[5][-1].append(['hide','yes'])
    return p

def text_node(txt,x,y,size=1.27):
    return ['text',Q(txt),['at',num(x),num(y),'0'],effects(size,'left bottom'),['uuid',stable('text:'+txt)]]

def globalize_labels(doc):
    # Global names intentionally match the PCB: local root labels export /NET.
    for node in doc:
        if not isinstance(node,list) or not node or node[0]!='label':continue
        node[0]='global_label';node.insert(2,['shape','input'])
        at=get(node,'at');ef=get(node,'effects');just=get(ef,'justify')
        at[3]='0' if 'right' in just else '180'
        node.append(field('Intersheetrefs','${INTERSHEET_REFS}',float(at[1]),float(at[2]),1.0,True))

def rebuild(manifest_path,output):
    manifest=json.loads(Path(manifest_path).read_text()); parts=copy.deepcopy(BASE_PARTS)
    footprint_map=json.loads((Path(manifest_path).parent/'revb_footprint_map.json').read_text())
    for p in manifest['parts']:
        ref=p['ref']; old=parts.get(ref,{}); old.update({k:p[k] for k in ['value','mpn','footprint','note']})
        if ref in NEW_PINS:old['pins']={no:{'name':name,'type':typ,'net':p['pins'][no]} for no,name,typ in NEW_PINS[ref]}
        elif ref not in parts:old['pins']={no:{'name':no,'type':'passive','net':net} for no,net in p['pins'].items()}
        else:
            for no,net in p['pins'].items():old['pins'][no]['net']=net
        parts[ref]=old
    for ref in manifest.get('remove_refs',[]):parts.pop(ref,None)
    for ref,pins in manifest['existing_pin_changes'].items():
        for no,net in pins.items():parts[ref]['pins'][no]['net']=net
    for ref,mpn in manifest.get('existing_mpn',{}).items():
        if ref not in parts:raise ValueError('MPN for absent ref '+ref)
        parts[ref]['mpn']=mpn
    parts['D1']['mpn']='WS2812B-V5/W'
    parts['U4']['mpn']='ESP32-PICO-D4'
    for ref,fp in footprint_map.items():
        if ref in parts:parts[ref]['footprint']=fp
    # Explicit revisions are authoritative while the PCB package map catches up.
    for revised in manifest['parts']:
        if revised['ref'] in parts:
            parts[revised['ref']]['footprint']=revised['footprint']
    if parts['A1'].get('mpn')=='CA-C03':
        parts['A1']['manufacturer']='CrossAir / Guangzhou Hanwuji Electronics'
    # Exported PCB symbols are repackaged by the PCB maintainer into this local library.
    for ref,p in parts.items():
        if ref not in POSITIONS:raise ValueError('Missing placement '+ref)
        if any(pin['net'] in manifest.get('remove_nets',[]) for pin in p['pins'].values()):raise ValueError('Retired net '+ref)
    doc=['kicad_sch',['version','20260306'],['generator','eeschema'],['generator_version',Q('10.0')],['uuid',Q(ROOT_UUID)],['paper',Q('A2')],
         ['title_block',['title',Q('HoloCubic Naive RevB — Main board')],['date',Q('2026-10-29')],['rev',Q('B')],['company',Q('HoloCubic / original design: peng-zhihui')],['comment','1',Q('Source Altium retained; MCU and sensor functional pin mapping preserved.')],['comment','2',Q('Engineering revision: ERC/netlist checks required; hardware validation pending.')]]]
    libs={}; specs={};libkeys={}
    for ref,p in parts.items():
        key=ref[0] if re.fullmatch(r'[RCL][0-9]+',ref) else ref
        if key not in libs:libs[key],pts,height=symbol_definition(key,p['pins']);specs[key]=(pts,height)
        libkeys[ref]=key
    doc.append(['lib_symbols',*[copy.deepcopy(s) for s in libs.values()]])
    for ref,p in parts.items():
        x,y=POSITIONS[ref];key=libkeys[ref];pts,height=specs[key]; sid=Q(p.get('uuid',str(stable('symbol:'+ref))))
        libid='HoloCubicRevB:'+key
        s=['symbol',['lib_id',Q(libid)],['at',num(x),num(y),'0'],['unit','1'],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',sid],
           field('Reference',ref,x,y-height/2-5.08,1.27),field('Value',p['value'],x,y-height/2-2.54,1.0),field('Footprint',p['footprint'],x,y,1.0,True),field('Datasheet','',x,y,1.0,True)]
        if p.get('mpn'):s.append(field('MPN',p['mpn'],x,y,1.0,True))
        if p.get('manufacturer'):s.append(field('Manufacturer',p['manufacturer'],x,y,1.0,True))
        if p.get('note'):s.append(field('DesignNote',p['note'],x,y,1.0,True))
        for no in p['pins']:s.append(['pin',Q(no),['uuid',stable('pin:'+ref+':'+no)]])
        s.append(['instances',['project',Q('MainBoard'),['path',Q('/'+ROOT_UUID),['reference',Q(ref)],['unit','1']]]]);doc.append(s)
        for no,pin in p['pins'].items():
            px,py,a=pts[no];px+=x;py=y-py; net=pin['net']
            if net is None:
                doc.append(['no_connect',['at',num(px),num(py)],['uuid',stable('nc:'+ref+':'+no)]]);continue
            ex=px+(-7.62 if a==0 else 7.62);ey=py
            doc.append(['wire',['pts',['xy',num(px),num(py)],['xy',num(ex),num(ey)]],['stroke',['width','0'],['type','default']],['uuid',stable('wire:'+ref+':'+no)]])
            doc.append(['label',Q(net),['at',num(ex),num(ey),'0'],effects(1.0,'left bottom' if a==180 else 'right bottom'),['uuid',stable('label:'+ref+':'+no)]])
    frames=[(10,15,205,160,'1  USB-C: USB 2.0 sink / ESD'),(210,15,410,168,'2  Delayed 5V load / 3.3V buck'),(415,15,580,160,'3  5V RGB with 3.3V-compatible input buffer'),(10,175,205,380,'4  USB-UART and automatic download / reset'),(210,175,410,310,'5  ESP32-PICO-D4 core / RF'),(415,175,580,310,'6  Motion / ambient light / I2C pull-ups'),(210,315,410,400,'7  microSD SPI / all DAT pull-ups'),(415,315,580,373,'8  FFC to display board')]
    for x1,y1,x2,y2,title in frames:
        rect=['polyline',['pts',['xy',num(x1),num(y1)],['xy',num(x2),num(y1)],['xy',num(x2),num(y2)],['xy',num(x1),num(y2)],['xy',num(x1),num(y1)]],['stroke',['width','0.254'],['type','default']],['fill',['type','none']],['uuid',stable('frame:'+title)]]
        doc += [rect,text_node(title,x1+2.54,y1+6.35,1.5)]
    notes=[('USB_VBUS = connector raw 5V; VDD_5V = switched system 5V.\nCC1 / CC2 each have an independent 5.1k Rd.',14,155),
           ('ON RC: 100k / 100nF; CT: 100pF C0G. 5V tR approx 0.425ms.\nMeasure CP_VDD rise to 2.7V <=1ms and USB hot-plug current.',214,164),
           ('OE permanently enabled; GPIO27 pulled low at reset.\nD1: Worldsemi WS2812B-V5/W. Series 33 ohm near buffer.',419,152),
           ('CP2102 internal 3.3V is CP_VDD, with C18 local bypass.\nR6 / C7 provide the ESP32 EN reset delay.\nDual NPN DTR/RTS topology retained from the original design.',14,369),
           ('Unused exposed flash / strapping / ADC pins are explicitly NC.\nGPIO32 = SDA; GPIO33 = SCL; GPIO27 = RGB.\nGPIO13/14/15/26 = SD CMD/CLK/CS/DAT0.\nGPIO18/23/2/4/5 = TFT SCK/MOSI/DC/RESET/BL.\nMPU6050: no exposed-pad pin; keep copper/vias/paste out below die.',214,306),
           ('MPU6050 address: 0x68 (AD0=GND); INT not used.\nBH1750 address: 0x23 (ADDR=GND). 4.7k I2C pull-ups.',419,306),
           ('FFC pin order retained. Mate reverses pin numbering.\nGPIO5 low enables the display NMOS / AL5802 backlight stage.\nPins 7=3V3, 8=switched VDD_5V.',419,370)]
    for t,x,y in notes:doc.append(text_node(t,x,y,1.0))
    # Genuine supply sources: USB host supplies raw VBUS/GND; R2 feeds the MCU branch.
    flag=['symbol',Q('PWR_FLAG'),['power'],['pin_names',['offset','0']],['exclude_from_sim','no'],['in_bom','no'],['on_board','no'],field('Reference','#FLG',0,4,1.0,True),field('Value','PWR_FLAG',0,3,1.0),['symbol',Q('PWR_FLAG_0_1'),line([(0,0),(0,1.27),(-1.27,2.54),(0,3.81),(1.27,2.54),(0,1.27)])],['symbol',Q('PWR_FLAG_1_1'),pin_node('1','pwr','power_out',0,0,90,0,False)]]
    get(doc,'lib_symbols').append(flag);libs['PWR_FLAG']=flag
    for i,net in enumerate(['USB_VBUS','GND','3V3A','3V3']):
        x=22.86+50.8*i;y=394.97
        doc.append(['symbol',['lib_id',Q('HoloCubicRevB:PWR_FLAG')],['at',num(x),num(y),'0'],['unit','1'],['in_bom','no'],['on_board','no'],['dnp','no'],['uuid',stable('flag:'+net)],field('Reference','#FLG%03d'%(i+1),x,y-5,1.0,True),field('Value','PWR_FLAG',x,y-5,1.0),['pin',Q('1'),['uuid',stable('flagpin:'+net)]],['instances',['project',Q('MainBoard'),['path',Q('/'+ROOT_UUID),['reference',Q('#FLG%03d'%(i+1))],['unit','1']]]]])
        doc.append(['label',Q(net),['at',num(x),num(y),'0'],effects(1.0,'left bottom'),['uuid',stable('flaglabel:'+net)]])
    # Embedded cache names include library prefix; standalone library uses leaf names.
    for l in alln(get(doc,'lib_symbols'),'symbol'):l[1]=Q('HoloCubicRevB:'+str(l[1]))
    globalize_labels(doc)
    write(output,doc)
    outdir=Path(output).parent
    write(outdir/'HoloCubicRevB.kicad_sym',['kicad_symbol_lib',['version','20241209'],['generator','kicad_symbol_editor'],*[copy.deepcopy(s) for s in libs.values()]])
    write(outdir/'sym-lib-table',['sym_lib_table',['version','7'],['lib',['name',Q('HoloCubicRevB')],['type',Q('KiCad')],['uri',Q('${KIPRJMOD}/HoloCubicRevB.kicad_sym')],['options',Q('')],['descr',Q('Local self-contained HoloCubic Naive RevB symbols')]]])
    # Manifest-derived expected nodes enables independent netlist comparison.
    expected={}
    for ref,p in parts.items():
        for no,pin in p['pins'].items():
            if pin['net']:expected.setdefault(pin['net'],[]).append([ref,no])
    (outdir/'schematic_expected_nets.json').write_text(json.dumps(expected,indent=2)+'\n')
    print('Wrote %d parts, %d real nets, local symbol library/table.'%(len(parts),len(expected)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source');p.add_argument('--output',required=True);p.add_argument('--manifest');p.add_argument('--annotate-only',action='store_true');a=p.parse_args()
    if a.annotate_only:annotate(a.source,a.output)
    else:rebuild(a.manifest,a.output)
