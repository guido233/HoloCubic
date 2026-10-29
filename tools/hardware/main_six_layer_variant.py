#!/usr/bin/env python3
"""Create a new six-layer RevB prototype PCB from a four-layer intermediate.

Run with KiCad 10's matching Python and -B. This is a migration step, not a
rebuild of the final routed PCB. It copies no schematic, project or libraries.
The 1.0192 mm stack is custom CAD bookkeeping, NOT a fabricator-confirmed stack.
No routing, zone refill, DRC, impedance or RF qualification is performed here.
"""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import uuid

import pcbnew as k

from mechanical_baseline import children, one, parse_sexpr


NOMINAL_MM = 1.0192
CAPABILITY_URL = "https://jlcpcb.com/resources/6-layer-pcbs"
STACK = [
    ("F.SilkS", "Top Silk Screen", None),
    ("F.Paste", "Top Solder Paste", None),
    ("F.Mask", "Top Solder Mask", 0.010),
    ("F.Cu", "copper", 0.035),
    ("dielectric 1", "prepreg", 0.0994),
    ("In1.Cu", "copper", 0.0152),
    ("dielectric 2", "core", 0.250),
    ("In2.Cu", "copper", 0.0152),
    ("dielectric 3", "prepreg", 0.1696),
    ("In3.Cu", "copper", 0.0152),
    ("dielectric 4", "core", 0.250),
    ("In4.Cu", "copper", 0.0152),
    ("dielectric 5", "prepreg", 0.0994),
    ("B.Cu", "copper", 0.035),
    ("B.Mask", "Bottom Solder Mask", 0.010),
    ("B.Paste", "Bottom Solder Paste", None),
    ("B.SilkS", "Bottom Silk Screen", None),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def point(p):
    return p.x, p.y


def replace_form(text, marker, replacement):
    """Replace one balanced native form without reserializing other objects."""
    start = text.index(marker)
    depth, quoted, escape = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[:start] + replacement + text[index + 1:]
    raise ValueError("Unclosed native form: " + marker)


def stack_form():
    lines = ["(stackup"]
    for name, kind, thickness in STACK:
        line = '(layer "' + name + '" (type "' + kind + '")'
        if thickness is not None:
            line += " (thickness " + format(thickness, ".4f") + ")"
        if kind in ("prepreg", "core"):
            line += ' (material "CUSTOM PROTOTYPE - fabricator confirmation required")'
        # No invented dielectric constant or loss tangent is supplied.
        lines.append(line + ")")
    lines += ['(copper_finish "None")', "(dielectric_constraints yes)", ")"]
    return "\n".join(lines)


def protected_native_forms(tree):
    """Include full footprint/model/metadata, every track/arc/via and drawing."""
    excluded = {"layers", "setup", "zone"}
    forms = [item for item in tree[1:]
             if not isinstance(item, list) or not item or item[0] not in excluded]
    setup = one(tree, "setup", [])
    forms.append([item for item in setup if not isinstance(item, list)
                  or not item or item[0] != "stackup"])
    return forms


def zone_definition(node, ignore_layers=False):
    # Fill polygons are derived data; final native DRC must refill all layers.
    ignored = {"filled_polygon", "fill_segments"}
    if ignore_layers:
        ignored.update(("layer", "layers"))
    return [item for item in node if not isinstance(item, list)
            or not item or item[0] not in ignored]


def zone_map(tree):
    return {one(node, "uuid")[1]: node for node in children(tree, "zone")}


def thermal_signature(board):
    pico = board.FindFootprintByReference("U4")
    require(pico is not None, "Expected RevB U4 ESP32-PICO footprint")
    x, y = point(pico.GetPosition())
    vias = sorted((point(v.GetPosition()), v.GetWidth(k.F_Cu), v.GetDrillValue(),
                   v.GetFrontTentingMode(), v.GetBackTentingMode(), v.IsLocked())
                  for v in board.GetTracks()
                  if isinstance(v, k.PCB_VIA) and v.GetNetname() == "GND"
                  and abs(v.GetPosition().x - x) < k.FromMM(2.25)
                  and abs(v.GetPosition().y - y) < k.FromMM(2.25))
    windows = sorted((point(p.GetPosition()), point(p.GetSize()))
                     for p in pico.Pads() if p.GetNumber() == ""
                     and p.IsOnLayer(k.F_Paste) and not p.IsOnLayer(k.F_Cu))
    require(len(vias) == 21 and len(windows) == 16,
            "Expected exactly 21 PICO thermal vias and 16 paste windows")
    return vias, windows


def rf_signature(board):
    pieces = sorted((t.m_Uuid.AsString(), point(t.GetStart()), point(t.GetEnd()),
                     point(t.GetMid()) if isinstance(t, k.PCB_ARC) else None,
                     t.GetWidth(), t.GetLayer(), t.IsLocked())
                    for t in board.GetTracks() if t.GetNetname() == "NetA1_1")
    require(len(pieces) == 7, "Expected all seven original outer RF pieces")
    return pieces


def require_ground_only(board, layers):
    for track in board.GetTracks():
        if not isinstance(track, k.PCB_VIA) and track.GetLayer() in layers:
            require(track.GetNetname() == "GND",
                    "Dedicated GND layer contains non-GND track "
                    + track.m_Uuid.AsString())


def convert(source, target):
    source, target = source.resolve(strict=True), target.resolve()
    require(source.suffix == ".kicad_pcb" and target.suffix == ".kicad_pcb",
            "Input and output must be .kicad_pcb files")
    require(source != target, "Output must not replace the source")
    report_path = target.with_suffix(".variant.json")
    require(not target.exists() and not report_path.exists(),
            "Output PCB and report must both be new paths")
    source_bytes = source.read_bytes()
    source_sha = digest(source_bytes)
    source_tree = parse_sexpr(source_bytes.decode("utf-8"))
    # Record paired project bytes as an additional guard against API side effects.
    project = source.with_suffix(".kicad_pro")
    project_bytes = project.read_bytes() if project.exists() else None
    board = k.LoadBoard(str(source))
    require(board.GetCopperLayerCount() == 4, "Input must have four copper layers")
    require(board.GetDesignSettings().GetBoardThickness() == k.FromMM(NOMINAL_MM),
            "Input must be the 1.0192 mm RevB four-layer intermediate")
    require_ground_only(board, {k.In1_Cu})
    before_rf, before_thermal = rf_signature(board), thermal_signature(board)
    originals = list(board.Zones())
    ground_models = [z for z in originals if not z.GetIsRuleArea()
                     and z.GetLayer() == k.B_Cu and z.GetNetname() == "GND"]
    require(len(ground_models) == 1, "Expected one B.Cu GND zone to copy")
    expanded = [z for z in originals if z.GetIsRuleArea()
                and z.GetLayerSet().Contains(k.In1_Cu)
                and z.GetLayerSet().Contains(k.In2_Cu)]
    require(len(expanded) == 3, "Expected exactly three inner RF keepouts")
    require(all(z.GetDoNotAllowTracks() and z.GetDoNotAllowVias()
                and z.GetDoNotAllowPads() and z.GetDoNotAllowZoneFills()
                for z in expanded), "Inner RF keepouts must prohibit all copper")
    expanded_ids = sorted(z.m_Uuid.AsString() for z in expanded)
    board.SetCopperLayerCount(6)
    board.GetDesignSettings().SetBoardThickness(k.FromMM(NOMINAL_MM))
    new_zone_ids = []
    for layer in (k.In3_Cu, k.In4_Cu):
        zone = k.Cast_to_ZONE(ground_models[0].Duplicate(False))
        new_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                              "holocubic-revb-six:" + source_sha + ":"
                              + board.GetLayerName(layer)))
        zone.SetUuid(k.KIID(new_id))
        zone.SetLayer(layer)
        zone.SetAssignedPriority(0)
        zone.UnFill()
        board.Add(zone)
        new_zone_ids.append(new_id)
    for zone in expanded:
        layers = zone.GetLayerSet()
        layers.AddLayer(k.In3_Cu)
        layers.AddLayer(k.In4_Cu)
        zone.SetLayerSet(layers)

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="holocubic-six-", dir=target.parent) as temp:
        staged = Path(temp) / target.name
        require(k.SaveBoard(str(staged), board), "KiCad could not save the new PCB")
        staged.write_text(replace_form(staged.read_text(), "(stackup", stack_form()))
        check = k.LoadBoard(str(staged))
        output_bytes = staged.read_bytes()
        output_tree = parse_sexpr(output_bytes.decode("utf-8"))
        require(check.GetCopperLayerCount() == 6, "Output layer count changed")
        require(protected_native_forms(source_tree) == protected_native_forms(output_tree),
                "A source copper object, footprint, model, metadata or drawing changed")
        old_zones, new_zones = zone_map(source_tree), zone_map(output_tree)
        require(set(new_zones) == set(old_zones) | set(new_zone_ids),
                "Unexpected zone added or removed")
        for zone_id, old in old_zones.items():
            ignore_layers = zone_id in expanded_ids
            require(zone_definition(old, ignore_layers)
                    == zone_definition(new_zones[zone_id], ignore_layers),
                    "Source zone definition changed: " + zone_id)
        for zone in check.Zones():
            zone_id = zone.m_Uuid.AsString()
            if zone_id in expanded_ids:
                require(all(zone.GetLayerSet().Contains(layer) for layer in
                            (k.In1_Cu, k.In2_Cu, k.In3_Cu, k.In4_Cu)),
                        "An inner RF keepout does not cover all four inner layers")
            if zone_id in new_zone_ids:
                require(not zone.GetIsRuleArea() and zone.GetNetname() == "GND"
                        and zone.GetLayer() in (k.In3_Cu, k.In4_Cu),
                        "New inner zone is not the expected GND pour")
        require(rf_signature(check) == before_rf, "Original RF geometry/arc/lock changed")
        require(thermal_signature(check) == before_thermal, "PICO thermal pattern changed")
        require_ground_only(check, {k.In1_Cu, k.In4_Cu})
        require(source.read_bytes() == source_bytes, "Source PCB changed")
        require(project_bytes is None or project.read_bytes() == project_bytes,
                "Paired source project changed")
        report = {
            "status": "CUSTOM_PROTOTYPE_STACK_NOT_MANUFACTURING_RELEASE",
            "input_sha256": source_sha,
            "output_sha256": digest(output_bytes),
            "copper_layers": ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"],
            "purpose": ["signals", "dedicated GND", "power and signals",
                        "signals and GND pour", "dedicated GND", "signals"],
            "nominal_cad_thickness_including_masks_mm": NOMINAL_MM,
            "stack_top_to_bottom": [
                {"name": name, "type": kind, "thickness_mm": thickness}
                for name, kind, thickness in STACK if thickness is not None],
            "expanded_RF_keepout_uuids": expanded_ids,
            "added_GND_zone_uuids": new_zone_ids,
            "all_source_native_objects_preserved": True,
            "source_zone_definitions_preserved_except_RF_layer_extension": True,
            "RF_pieces_including_arc_midpoints_preserved": 7,
            "PICO_thermal_vias_preserved": 21,
            "PICO_paste_windows_preserved": 16,
            "capability_reference_only": CAPABILITY_URL,
            "fabrication_confirmation_required": [
                "Exact materials, copper/core/prepreg accounting and finished thickness tolerance",
                "Nominal 1.0 mm six-layer capability does not confirm this custom stack",
                "Dielectric properties and impedance are unspecified; RF needs VNA/enclosure validation"],
            "not_performed": ["routing", "zone refill", "native DRC/schematic parity",
                              "physical assembly", "electrical or RF qualification"],
        }
        # Exclusive creation prevents an accidental overwrite even after validation.
        with target.open("xb") as handle:
            handle.write(output_bytes)
        try:
            with report_path.open("x") as handle:
                json.dump(report, handle, indent=2)
                handle.write("\n")
        except Exception:
            target.unlink()
            raise
    return report_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="four-layer RevB intermediate PCB")
    parser.add_argument("output", type=Path, help="new six-layer PCB path (must not exist)")
    args = parser.parse_args()
    # Native load/save can access fonts and settings even without an editor UI.
    import wx
    app = wx.App(False) if wx.GetApp() is None else None
    try:
        require(abs(sum(t for _, _, t in STACK if t is not None) - NOMINAL_MM) < 1e-9,
                "Internal stack thickness sum is inconsistent")
        report = convert(args.input, args.output)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, "six-layer conversion failed: " + str(error) + "\n")
    finally:
        if app is not None:
            app.Destroy()
    print("Created prototype six-layer copy:", args.output)
    print("Preservation report:", report)
    print("Refill and run native DRC/parity before accepting any routed result.")


if __name__ == "__main__":
    # KiCad's bundled wx runtime can hang during Python's GUI teardown after a
    # headless native save. All file/context cleanup above completes first.
    import os
    import sys
    import traceback
    try:
        main()
        exit_code = 0
    except SystemExit as error:
        exit_code = error.code if isinstance(error.code, int) else 1
    except Exception:
        traceback.print_exc()
        exit_code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
