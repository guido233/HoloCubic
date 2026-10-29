#!/usr/bin/env python3
"""Apply the reviewed Main RevB copper delta to a separate native-board copy.

Uses the standard-library S-expression reader already used by the schematic
generator. Only explicitly listed track/via blocks and reviewed footprint_changes
change; zones, rules and all other text remain untouched. The input is never
overwritten. A footprint change includes its complete before/after block so the
source must match, rather than silently moving an independently edited component.

Default data reproduce Power6 from the four-layer two-row geometry freeze. A
later bridge delta can be selected with --delta. Copy the matching project,
schematic and libraries alongside the output, then refill zones and run native
KiCad DRC with schematic parity. Applying copper is not manufacturing acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path

from revise_schematic import dump, get, parse


def copper_blocks(text, include_footprints=False):
    """Find top-level native copper blocks without rewriting unrelated content."""
    depth = 0
    quoted = escaped = False
    start = None
    result = {}
    for i, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == '(':
            if depth == 1:
                start = i
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 1 and start is not None:
                raw = text[start:i + 1]
                kind = raw[1:].split(None, 1)[0]
                if kind in ('segment', 'via', 'arc') or (include_footprints and kind == 'footprint'):
                    node = parse(raw)
                    uid = str(get(node, 'uuid')[1])
                    if uid in result:
                        raise ValueError('Duplicate copper UUID: ' + uid)
                    result[uid] = (start, i + 1, dump(node))
                start = None
    if depth or quoted:
        raise ValueError('Malformed native board')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--delta', type=Path, default=Path(__file__).with_name('data') / 'main_power_route_delta.json')
    ap.add_argument('--allow-extra-copper', action='store_true', help='Permit a board with separately reviewed copper; changed source UUIDs must still match exactly')
    args = ap.parse_args()
    if args.input.resolve() == args.output.resolve() or args.output.exists():
        raise ValueError('Output must be a new file, distinct from the input')
    data = json.loads(args.delta.read_text())
    raw = args.input.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != data['source_sha256'] and not args.allow_extra_copper:
        raise ValueError('Unexpected source SHA256; use the documented geometry freeze')
    text = raw.decode('utf-8')
    with_footprints = bool(data.get('footprint_changes'))
    blocks = copper_blocks(text, with_footprints)
    edits = []
    changes = data['changes'] + data.get('footprint_changes', [])
    for change in changes:
        uid = change['uuid']
        if uid not in blocks or blocks[uid][2] != dump(parse(change['before'])):
            raise ValueError('Source copper changed or missing: ' + uid)
        start, end, _ = blocks[uid]
        edits.append((start, end, change['after'] or ''))
    additions = []
    for raw_node in data['add']:
        node = parse(raw_node)
        uid = str(get(node, 'uuid')[1])
        if uid in blocks:
            raise ValueError('Added UUID already exists: ' + uid)
        additions.append(raw_node)
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    end = text.rfind(')')
    text = text[:end] + ''.join('\n\t' + n.replace('\n', '\n\t') for n in additions) + '\n' + text[end:]
    output_blocks = copper_blocks(text, with_footprints)
    for change in changes:
        expected = change['after']
        if expected is None:
            assert change['uuid'] not in output_blocks
        else:
            assert output_blocks[change['uuid']][2] == dump(parse(expected))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(json.dumps({'output': str(args.output), 'source_sha256': sha,
                      'changed_or_removed': len(edits), 'added': len(additions),
                      'next_step': 'Native zone refill, all-rule DRC and schematic parity are required'}, indent=2))


if __name__ == '__main__':
    main()
