#!/usr/bin/env python3
"""Export real component-terminal coordinates for first-article measurements.

No PCB edits or extra test pads. Coordinates and nets come from current boards;
the drawings distinguish front and rear views. Access after assembly is manual.
"""
import argparse
import csv
import hashlib
import html
import json
from pathlib import Path

from mechanical_baseline import read_kicad, edge_points

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / '1.Hardware/RevB-KiCad/Naive'
TARGETS = {
    'MainBoard': [
        ('M1', 'C15', '1', 'USB_VBUS'), ('M2', 'C20', '1', 'VDD_5V'),
        ('M3', 'C18', '1', 'CP_VDD'), ('M4', 'C13', '1', '3V3'),
        ('M5', 'C4', '2', '3V3A'), ('M6', 'C7', '1', 'EN'),
        ('M7', 'C20', '2', 'GND'), ('M8', 'R12', '1', 'USB_CC1'),
        ('M9', 'R13', '1', 'USB_CC2'),
        ('M10', 'C11', '1', '3V3'), ('M11', 'C24', '1', 'NetR11_1'),
    ],
    'ExtendBoard': [
        ('E1', 'C3', '1', 'VDD_5V'), ('E2', 'C1', '1', '3V3'),
        ('E3', 'R2', '1', 'BL_SENSE'), ('E4', 'R2', '2', 'GND'),
    ],
}


def export(destination):
    destination.mkdir(parents=True, exist_ok=True)
    rows, boards, sources = [], {}, []
    for name, targets in TARGETS.items():
        path = BASE / name / (name + '.kicad_pcb')
        board = read_kicad(path)
        boards[name] = board
        sources.append({'path': str(path.relative_to(ROOT)),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for label, ref, number, net in targets:
            pads = [p for p in board['components'][ref]['pads'] if p['number'] == number]
            if len(pads) != 1:
                raise ValueError('Probe terminal is not unique: ' + name + ':' + ref + '.' + number)
            pad = pads[0]
            if pad['net_hint'] != net:
                raise ValueError(f'{name}:{ref}.{number} expected {net}, got {pad["net_hint"]}')
            sides = [side for side in ['F', 'B'] if side + '.Cu' in pad['layers']]
            if len(sides) != 1 or sides[0] + '.Mask' not in pad['layers']:
                raise ValueError('Probe terminal is not a single exposed surface terminal')
            rows.append({'id': label, 'board': name, 'reference': ref, 'pad': number,
                         'net': net, 'side': sides[0],
                         'x_mm': round(pad['at_mm'][0], 6), 'y_mm': round(pad['at_mm'][1], 6),
                         'kind': 'existing component terminal; tip access must be checked'})
    result = {'scope': 'Engineering coordinate guide, not a bed-of-nails fixture or measured result.',
              'sources': sources, 'terminals': rows,
              'notes': ['Use a ground spring or short ground connection; check tip clearance before powering.',
                        'Do not substitute the 100pF LOAD_CT node for a supply test point; probe capacitance changes timing.',
                        'Measure backlight current from voltage across the actual 27ohm R2; PWM duty is not a current reading.',
                        'For BH1750 reset capture M10/VCC and M11/DVI together; confirm DVI <=0.4V for >=1us after VCC reaches 2.4V.',
                        'B-side drawings mirror X. CSV and JSON always retain native CAD coordinates.']}
    (destination / 'probe-map.json').write_text(json.dumps(result, indent=2) + '\n')
    with (destination / 'probe-map.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    draw(boards, rows, destination / 'probe-map.svg')
    return result


def draw(boards, rows, output):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">',
           '<rect width="210" height="297" fill="white"/>',
           '<style>text{font-family:Arial,sans-serif;fill:#182530} .edge{fill:none;stroke:#253b45;stroke-width:.3}</style>',
           '<text x="10" y="12" font-size="5">Naive RevB component-terminal probe map</text>',
           '<text x="10" y="19" font-size="3">Positions from native CAD. Drawings enlarged; not a fabrication or fixture drawing.</text>']
    for column, (name, board) in enumerate(boards.items()):
        outline = [edge_points(e) for e in board['outline']]
        points = [p for edge in outline for p in edge]
        xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
        ymin = min(p[1] for p in points)
        scale, left = 2.2, 12 + column * 99
        for row, side in enumerate(['F', 'B']):
            top = 33 + row * 91
            def xy(p):
                return (left + ((p[0] - xmin) if side == 'F' else (xmax - p[0])) * scale,
                        top + (p[1] - ymin) * scale)
            svg.append(f'<text x="{left}" y="{top-5}" font-size="3.5">{name} {side}-side view</text>')
            for edge in outline:
                data = ' '.join(f'{x:.4f},{y:.4f}' for x, y in map(xy, edge))
                svg.append(f'<polyline class="edge" points="{data}"/>')
            for pad in board['pads']:
                if side + '.Cu' not in pad['layers']:
                    continue
                x, y = xy(pad['at_mm'])
                svg.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r=".35" fill="#c3cdd2"/>')
            for target in rows:
                if target['board'] != name or target['side'] != side:
                    continue
                x, y = xy([target['x_mm'], target['y_mm']])
                svg.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r="1.1" fill="#c13d29"/>')
                svg.append(f'<text x="{x+1.4:.4f}" y="{y-1.2:.4f}" font-size="2.6">{target["id"]}</text>')
    per_column = (len(rows) + 1) // 2
    for index, target in enumerate(rows):
        text = f'{target["id"]}: {target["reference"]}.{target["pad"]} {target["net"]} ({target["side"]})'
        x, y = 12 + (index // per_column) * 98, 219 + (index % per_column) * 6
        svg.append(f'<text x="{x}" y="{y}" font-size="3.4">{html.escape(text)}</text>')
    svg += ['<text x="12" y="270" font-size="3">Check pad reference and polarity before attaching a probe.</text>',
            '<text x="12" y="277" font-size="3">No waveform, power-up, thermal or RF result is implied by this drawing.</text>', '</svg>']
    output.write_text('\n'.join(svg) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE / 'Closure')
    args = parser.parse_args()
    result = export(args.output)
    print('Exported', len(result['terminals']), 'current component-terminal positions to', args.output)
