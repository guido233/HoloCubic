#!/usr/bin/env python3
"""Check a KiCad board against the original Altium mechanical interface geometry.

Python 3.9+, standard library only. Examples, from the repository root::

    python3 tools/hardware/mechanical_baseline.py sources
    python3 tools/hardware/mechanical_baseline.py check Naive_MainBoard revision.kicad_pcb
    python3 tools/hardware/mechanical_baseline.py check Naive_ExtendBoard revision.kicad_pcb --map-ref 1=LCD1
    python3 tools/hardware/mechanical_baseline.py check Naive_MainBoard revb.kicad_pcb --connector-revision fh12
    python3 tools/hardware/mechanical_baseline.py check Naive_MainBoard revb.kicad_pcb --revision naive-revb

The baseline is a frozen extraction of the four original PcbDoc files, identified
by SHA256. It is not a fabrication/assembly approval. The checker reads KiCad 6+
S-expressions directly; it does not load plugins, execute code, or modify boards.
Only the recorded connector/LED/sensor interfaces are locked in the historical
baseline. A1 is advisory there; the explicit RevB profile locks the selected
CA-C03 pose/custom lands and the explicit U4 thermal land/stencil/via revision.
Unrecorded internal components may move.
An explicit connector revision checks the replacement geometry; it does not
silently skip the connector or overwrite the historical Altium baseline.

Format reference: https://dev-docs.kicad.org/en/file-formats/sexpr-intro/
"""

import argparse
import copy
import hashlib
import json
import math
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
TOKEN = re.compile(r'\s+|;[^\n]*|\(|\)|"(?:\\.|[^"\\])*"|[^\s();"]+')


def parse_sexpr(text):
    """Read the documented list/string/atom subset; reject truncated input."""
    stack, roots, end = [], [], 0
    for match in TOKEN.finditer(text):
        if text[end:match.start()].strip():
            raise ValueError("invalid KiCad token")
        token, end = match.group(), match.end()
        if token.isspace() or token.startswith(";"):
            continue
        if token == "(":
            node = []
            (stack[-1] if stack else roots).append(node)
            stack.append(node)
            if len(stack) > 100:
                raise ValueError("excessive KiCad nesting")
        elif token == ")":
            if not stack:
                raise ValueError("unmatched closing parenthesis")
            stack.pop()
        else:
            if not stack:
                raise ValueError("atom outside KiCad root")
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    if stack or text[end:].strip() or len(roots) != 1:
        raise ValueError("truncated file or multiple KiCad roots")
    return roots[0]


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def one(node, key, default=None):
    values = children(node, key)
    if len(values) > 1:
        raise ValueError(f"duplicate {key} field")
    return values[0] if values else default


def xy(node):
    if node is None or len(node) < 3:
        raise ValueError("missing 2D coordinate")
    result = [float(node[1]), float(node[2])]
    if not all(math.isfinite(x) for x in result):
        raise ValueError("non-finite coordinate")
    return result


def finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("non-finite KiCad dimension/angle")
    return result


def rotate(point, angle):
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [c * point[0] - s * point[1], s * point[0] + c * point[1]]


def transform(point, pose):
    point = rotate(point, pose[0])
    return [point[0] + pose[1], point[1] + pose[2]]


def arc_points(start, mid, end, step=0.1):
    """Tessellate a three-point circular arc, including the declared midpoint side."""
    ax, ay = start
    bx, by = mid
    cx, cy = end
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        raise ValueError("collinear/degenerate Edge.Cuts arc")
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    center = [(a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d,
              (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d]
    radius = math.dist(start, center)
    angles = [math.atan2(p[1] - center[1], p[0] - center[0]) for p in (start, mid, end)]
    sweep = (angles[2] - angles[0]) % math.tau
    if (angles[1] - angles[0]) % math.tau > sweep + 1e-9:
        sweep -= math.tau
    # Both 0.1mm spacing and <=0.001mm chord sagitta, independent of radius.
    angular_step = min(step / radius, 2 * math.acos(max(-1, 1 - 0.001 / radius)))
    count = max(2, math.ceil(abs(sweep) / angular_step))
    if count > 50000:
        raise ValueError("unreasonably large Edge.Cuts arc")
    points = [[center[0] + radius * math.cos(angles[0] + sweep * i / count),
               center[1] + radius * math.sin(angles[0] + sweep * i / count)] for i in range(count + 1)]
    points[0], points[-1] = list(start), list(end)
    return points


def edge_points(edge):
    if edge["type"] == "arc":
        return arc_points(edge["start_mm"], edge["mid_mm"], edge["end_mm"])
    start, end = edge["start_mm"], edge["end_mm"]
    count = max(1, math.ceil(math.dist(start, end) / 0.1))
    if count > 50000:
        raise ValueError("unreasonably long Edge.Cuts line")
    return [[a + (b - a) * i / count for a, b in zip(start, end)] for i in range(count + 1)]


def graphics_edges(node, pose=(0, 0, 0)):
    """Fail closed on unsupported Edge.Cuts graphics instead of ignoring them."""
    result = []
    for item in node:
        if not isinstance(item, list) or not item or not str(item[0]).startswith(("gr_", "fp_")):
            continue
        if one(item, "layer", [None, None])[1] != "Edge.Cuts":
            continue
        kind = item[0].split("_", 1)[1]
        def point(key):
            return transform(xy(one(item, key)), pose)
        if kind in ("line", "arc"):
            edge = {"type": kind, "start_mm": point("start"), "end_mm": point("end")}
            if kind == "arc":
                edge["mid_mm"] = point("mid")  # Legacy center/angle arcs deliberately rejected.
            result.append(edge)
        elif kind == "rect":
            a, b = xy(one(item, "start")), xy(one(item, "end"))
            points = [a, [b[0], a[1]], b, [a[0], b[1]]]
            for start, end in zip(points, points[1:] + points[:1]):
                result.append({"type": "line", "start_mm": transform(start, pose), "end_mm": transform(end, pose)})
        elif kind == "poly":
            points = [transform(xy(p), pose) for p in children(one(item, "pts", []), "xy")]
            if len(points) < 3:
                raise ValueError("invalid Edge.Cuts polygon")
            for start, end in zip(points, points[1:] + points[:1]):
                result.append({"type": "line", "start_mm": start, "end_mm": end})
        elif kind == "circle":
            center, end = point("center"), point("end")
            dx, dy = end[0] - center[0], end[1] - center[1]
            other = [center[0] - dx, center[1] - dy]
            for a, b, sign in ((end, other, 1), (other, end, -1)):
                result.append({"type": "arc", "start_mm": a, "end_mm": b,
                               "mid_mm": [center[0] - sign * dy, center[1] + sign * dx]})
        else:
            raise ValueError(f"unsupported Edge.Cuts primitive: {item[0]}")
    return result


def read_kicad(path):
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("board exceeds the 50MiB checker input limit")
    root = parse_sexpr(path.read_text(encoding="utf-8"))
    if not root or root[0] != "kicad_pcb":
        raise ValueError("expected a KiCad board")
    general = one(root, "general", [])
    thickness = finite(one(general, "thickness", [None, "nan"])[1])
    result = {"thickness_mm": thickness, "components": {}, "pads": [], "vias": [], "outline": graphics_edges(root),
              "copper_layers": [x[1] for x in one(root, "layers", [None])[1:]
                                if isinstance(x, list) and len(x) > 2 and x[1].endswith(".Cu")],
              "stackup": [], "zones": [], "copper_tracks": []}
    net_names = {str(n[1]): n[2] for n in children(root, "net") if len(n) == 3}
    def net_name(item):
        net = one(item, "net", [None, ""])[-1]
        return net_names.get(str(net), net)
    for layer in children(one(one(root, "setup", []), "stackup", []), "layer"):
        result["stackup"].append({"name": layer[1], "type": one(layer, "type", [None, ""])[1],
                                  "thickness_mm": finite(one(layer, "thickness")[1])
                                  if one(layer, "thickness") else None})
    for zone in children(root, "zone"):
        single_layer = one(zone, "layer")
        result["zones"].append({"layers": [single_layer[1]] if single_layer else one(zone, "layers", [None])[1:],
                                "net_hint": net_name(zone),
                                "keepout": {x[0]: x[1] for x in one(zone, "keepout", [])[1:] if isinstance(x, list)},
                                "polygons": [[xy(p) for p in children(one(poly, "pts", []), "xy")]
                                             for poly in children(zone, "polygon")]})
    for item in children(root, "segment") + children(root, "arc"):
        result["copper_tracks"].append({"layer": one(item, "layer", [None, ""])[1], "net_hint": net_name(item)})
    for item in children(root, "via"):
        net = one(item, "net", [None, ""])[-1]
        tenting = one(item, "tenting", [])
        result["vias"].append({"at_mm": xy(one(item, "at")),
                               "size_mm": finite(one(item, "size")[1]),
                               "drill_mm": finite(one(item, "drill")[1]),
                               "layers": one(item, "layers", [None])[1:],
                               "net_hint": net_names.get(str(net), net),
                               "locked": one(item, "locked", [None, "no"])[-1] == "yes",
                               "tenting": {x[0]: x[1] for x in tenting[1:] if isinstance(x, list)}})
    for fp in children(root, "footprint") + children(root, "module"):
        reference = next((p[2] for p in children(fp, "property") if p[1] == "Reference"), None)
        if reference is None:
            reference = next((p[2] for p in children(fp, "fp_text") if p[1] == "reference"), None)
        at = one(fp, "at")
        position = xy(at)
        angle = -finite(at[3]) if len(at) > 3 else 0.0
        pose = [angle, *position]
        component = {"reference": reference, "at_mm": position, "angle_deg": angle,
                     "side": one(fp, "layer", [None, ""])[1], "pads": []}
        if reference:
            if reference in result["components"]:
                raise ValueError(f"duplicate footprint reference: {reference}")
            result["components"][reference] = component
        result["outline"].extend(graphics_edges(fp, pose))
        for item in children(fp, "pad"):
            at = one(item, "at")
            layers = one(item, "layers", [None])[1:]
            copper = "*.Cu" if "*.Cu" in layers or ("F.Cu" in layers and "B.Cu" in layers) else next((x for x in layers if x.endswith(".Cu")), "")
            drill = one(item, "drill")
            hole = None
            offset = [0.0, 0.0]
            if drill:
                values = [x for x in drill[1:] if not isinstance(x, list)]
                if values[0] == "oval":
                    hole = [finite(values[1]), finite(values[2])]
                else:
                    hole = [finite(values[0])] * 2
                if min(hole) <= 0:
                    raise ValueError("non-positive KiCad drill diameter")
                if one(drill, "offset"):
                    offset = xy(one(drill, "offset"))
            net = one(item, "net", [None, None])
            pad = {"reference": reference, "number": item[1], "at_mm": transform(xy(at), pose),
                   "size_mm": xy(one(item, "size")),
                   # KiCad pad angle is absolute, while pad X/Y is footprint-relative.
                   "angle_deg": -finite(at[3]) if len(at) > 3 else 0.0,
                   "copper": copper, "shape": item[3], "drill_mm": hole, "drill_offset_mm": offset,
                   "plated": item[2] != "np_thru_hole" if hole else None,
                   "roundrect_ratio": finite(one(item, "roundrect_rratio", [None, 0])[1]),
                   "net_hint": net_names.get(str(net[-1]), net[-1]) if len(net) >= 2 else None,
                   "layers": layers,
                   "solder_mask_margin_mm": finite(one(item, "solder_mask_margin", [None, 0])[1]),
                   "chamfer_ratio": finite(one(item, "chamfer_ratio", [None, 0])[1]),
                   "chamfer_corners": one(item, "chamfer", [None])[1:]}
            component["pads"].append(pad)
            result["pads"].append(pad)
    if not result["outline"]:
        raise ValueError("no Edge.Cuts geometry found")
    return result


def point_segment_distance(point, start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length2 = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length2)) if length2 else 0
    return math.dist(point, [start[0] + t * dx, start[1] + t * dy])


def outline_error(expected, actual, pose):
    a = [[transform(p, pose) for p in edge_points(e)] for e in expected]
    b = [edge_points(e) for e in actual]
    def directed(polylines, target):
        segments = [(x, y) for line in target for x, y in zip(line, line[1:])]
        return max(min(point_segment_distance(p, x, y) for x, y in segments) for line in polylines for p in line)
    return max(directed(a, b), directed(b, a))


def angle_error(a, b, period=360):
    return abs((a - b + period / 2) % period - period / 2)


def check_board(baseline, current, tolerance=0.025, thickness_tolerance=0.1, references=None):
    references = references or {}
    problems, used = [], set()
    def target_ref(ref):
        return references.get(ref, ref)
    def anchor_point(anchor, original):
        ref = anchor["ref"] if original else target_ref(anchor["ref"])
        comps = baseline["components"] if original else current["components"].values()
        matches = [p for c in comps if c["reference"] == ref for p in c["pads"] if p["number"] == anchor["pad"]]
        if len(matches) != 1:
            raise ValueError(f"alignment pad {ref}.{anchor['pad']} is missing or ambiguous")
        return matches[0]["at_mm"]
    a, b = [anchor_point(x, True) for x in baseline["alignment_pads"]]
    c, d = [anchor_point(x, False) for x in baseline["alignment_pads"]]
    if min(math.dist(a, b), math.dist(c, d)) < 1:
        raise ValueError("alignment pads are coincident or too close")
    angle = math.degrees(math.atan2(d[1] - c[1], d[0] - c[0]) - math.atan2(b[1] - a[1], b[0] - a[0]))
    rotated = rotate(a, angle)
    pose = [angle, c[0] - rotated[0], c[1] - rotated[1]]
    if abs(math.dist(a, b) - math.dist(c, d)) > tolerance:
        problems.append("alignment pad pitch changed")
    error = outline_error(baseline["outline"], current["outline"], pose)
    if error > tolerance:
        problems.append(f"board outline differs by up to {error:.6f}mm")
    thickness = current["thickness_mm"]
    nominal = baseline["stackup"]["copper_and_dielectric_mm"]
    if not math.isfinite(thickness) or abs(thickness - nominal) > thickness_tolerance:
        problems.append(f"board thickness {thickness}mm differs from source stack {nominal}mm")

    def check_pad(expected, actual, label):
        used.add(id(actual))
        if math.dist(transform(expected["at_mm"], pose), actual["at_mm"]) > tolerance:
            problems.append(f"{label}: pad/hole position changed")
        if expected["copper"] != actual["copper"]:
            problems.append(f"{label}: copper side changed ({expected['copper']} -> {actual['copper']})")
        if expected["shape"] != actual["shape"]:
            problems.append(f"{label}: copper pad shape changed")
        def dimensions_match(size, actual_size):
            return all(abs(x - y) <= tolerance for x, y in zip(size, actual_size))
        same, swapped = dimensions_match(expected["size_mm"], actual["size_mm"]), dimensions_match(expected["size_mm"], actual["size_mm"][::-1])
        desired_angle = expected["angle_deg"] + pose[0]
        circular = expected["shape"] == "circle" and abs(expected["size_mm"][0] - expected["size_mm"][1]) < tolerance
        if not ((same and (circular or angle_error(desired_angle, actual["angle_deg"], 180) <= 0.2)) or
                (swapped and angle_error(desired_angle + 90, actual["angle_deg"], 180) <= 0.2)):
            problems.append(f"{label}: pad size/orientation changed")
        if expected["shape"] == "roundrect" and abs(expected["roundrect_ratio"] - actual["roundrect_ratio"]) > 0.005:
            problems.append(f"{label}: rounded pad corner ratio changed")
        for field in ("layers", "chamfer_corners"):
            if field in expected and sorted(expected[field]) != sorted(actual[field]):
                problems.append(f"{label}: {field} changed")
        for field in ("solder_mask_margin_mm", "chamfer_ratio"):
            if field in expected and abs(expected[field] - actual[field]) > 0.001:
                problems.append(f"{label}: {field} changed")
        expected_hole, actual_hole = expected["drill_mm"], actual["drill_mm"]
        hole_matches = bool(expected_hole) == bool(actual_hole)
        if expected_hole and actual_hole:
            round_hole = abs(expected_hole[0] - expected_hole[1]) < tolerance
            hole_matches = ((dimensions_match(expected_hole, actual_hole) and
                             (round_hole or angle_error(desired_angle, actual["angle_deg"], 180) <= 0.2)) or
                            (dimensions_match(expected_hole, actual_hole[::-1]) and
                             angle_error(desired_angle + 90, actual["angle_deg"], 180) <= 0.2))
        if not hole_matches:
            problems.append(f"{label}: drill size/type changed")
        if expected["plated"] != actual["plated"]:
            problems.append(f"{label}: hole plating changed")
        if math.hypot(*actual["drill_offset_mm"]) > tolerance:
            problems.append(f"{label}: drill offset changed")

    for component in baseline["components"]:
        if not component["locked"]:
            continue
        ref = target_ref(component["reference"])
        actual = current["components"].get(ref)
        if not actual:
            problems.append(f"missing locked component {ref}")
            continue
        if component["side"] != actual["side"]:
            problems.append(f"{ref}: footprint body side changed")
        if math.dist(transform(component["at_mm"], pose), actual["at_mm"]) > tolerance:
            problems.append(f"{ref}: footprint origin changed")
        if angle_error(component["angle_deg"] + pose[0], actual["angle_deg"]) > 0.2:
            problems.append(f"{ref}: footprint orientation changed")
        if len(component["pads"]) != len(actual["pads"]):
            problems.append(f"{ref}: pad count changed")
        available = list(actual["pads"])
        for pad in component["pads"]:
            matches = [p for p in available if p["number"] == pad["number"]]
            if not matches:
                problems.append(f"missing locked pad {ref}.{pad['number']}")
                continue
            found = min(matches, key=lambda p: math.dist(transform(pad["at_mm"], pose), p["at_mm"]))
            available.remove(found)
            check_pad(pad, found, f"{ref}.{pad['number']}")
    for i, pad in enumerate(baseline["standalone_pads"]):
        candidates = [p for p in current["pads"] if id(p) not in used and p["drill_mm"]]
        if not candidates:
            problems.append(f"missing standalone {pad['role']} #{i + 1}")
            continue
        found = min(candidates, key=lambda p: math.dist(transform(pad["at_mm"], pose), p["at_mm"]))
        check_pad(pad, found, f"{pad['role']} #{i + 1}")
    for pad in current["pads"]:
        if pad["drill_mm"] and id(pad) not in used:
            problems.append(f"additional unreviewed drilled pad {pad['reference']}.{pad['number']}")
    for spec in baseline.get("placement_constraints", []):
        actual = current["components"].get(target_ref(spec["reference"]))
        if (not actual or actual["side"] != spec["side"] or
                math.dist(transform(spec["at_mm"], pose), actual["at_mm"]) > tolerance or
                angle_error(spec["angle_deg"] + pose[0], actual["angle_deg"]) > 0.2):
            problems.append(f"{spec['reference']}: reviewed RevB placement changed")
    rules = baseline.get("layer_rules")
    if rules:
        if current.get("copper_layers") != rules["copper_layers"]:
            problems.append("reviewed RevB copper-layer stack changed")
        if abs(current["thickness_mm"] - rules["nominal_total_thickness_mm"]) > 0.001:
            problems.append("reviewed RevB nominal total thickness changed")
        actual_stack = {x["name"]: x for x in current.get("stackup", [])}
        for layer in rules["stackup"]:
            actual = actual_stack.get(layer["name"])
            if (not actual or actual["type"] != layer["type"] or actual["thickness_mm"] is None or
                    abs(actual["thickness_mm"] - layer["thickness_mm"]) > 0.001):
                problems.append(f"reviewed stackup layer changed: {layer['name']}")
        def polygon_matches(expected, actual):
            if len(actual) < 3:
                return False
            def edges(points):
                return [{"type": "line", "start_mm": a, "end_mm": b}
                        for a, b in zip(points, points[1:] + points[:1])]
            # The original top/bottom antenna outlines differ by only ~0.03mm.
            # Do not let normal pad-placement tolerance substitute one for the
            # other after a keepout flag is weakened.
            return outline_error(edges(expected), edges(actual), pose) <= min(tolerance, 0.001)
        for keepout in rules["required_keepouts"]:
            if not any(set(keepout["layers"]).issubset(z["layers"]) and
                       all(z["keepout"].get(k) == v for k, v in keepout["flags"].items()) and
                       any(polygon_matches(keepout["polygon_mm"], p) for p in z["polygons"])
                       for z in current.get("zones", [])):
                problems.append(f"missing/changed inner RF keepout: {keepout['name']}")
        planes = rules.get("required_ground_planes")
        if planes is None:
            planes = [rules["required_ground_plane"]]
        for plane in planes:
            if not any(z["layers"] == [plane["layer"]] and not z["keepout"] and z["net_hint"] == "GND" and
                       any(polygon_matches(plane["polygon_mm"], p) for p in z["polygons"])
                       for z in current.get("zones", [])):
                problems.append(f"missing/changed reviewed GND plane outline: {plane['layer']}")
            if (any(t["layer"] == plane["layer"] and t["net_hint"] != "GND" for t in current.get("copper_tracks", [])) or
                    any(plane["layer"] in z["layers"] and not z["keepout"] and z["net_hint"] != "GND"
                        for z in current.get("zones", []))):
                problems.append(f"non-GND routing/zone breaks the reviewed ground-plane intent: {plane['layer']}")
    for spec in baseline.get("thermal_vias", []):
        center = transform(spec["center_mm"], pose)
        angle = spec["angle_deg"] + pose[0]
        def local(point):
            return rotate([point[0] - center[0], point[1] - center[1]], -angle)
        candidates = [v for v in current.get("vias", [])
                      if max(map(abs, local(v["at_mm"]))) <= spec["selection_half_width_mm"]]
        if len(candidates) != len(spec["local_centers_mm"]):
            problems.append(f"{spec['reference']}: thermal via count changed")
        for point in spec["local_centers_mm"]:
            target = transform(point, [angle, *center])
            matches = [v for v in candidates if math.dist(v["at_mm"], target) <= tolerance]
            if len(matches) != 1:
                problems.append(f"{spec['reference']}: thermal via missing/ambiguous at {point}")
                continue
            via = matches[0]
            if (abs(via["size_mm"] - spec["size_mm"]) > tolerance or
                    abs(via["drill_mm"] - spec["drill_mm"]) > tolerance or
                    set(via["layers"]) != set(spec["layers"]) or via["net_hint"] != spec["net"] or
                    not via["locked"] or via["tenting"] != spec["tenting"]):
                problems.append(f"{spec['reference']}: thermal via size/layers/net/lock/tenting changed")
    return {"passed": not problems, "alignment": {"rotation_deg": pose[0], "translation_mm": pose[1:]},
            "maximum_outline_error_mm": error, "problems": problems,
            "assembly_status": baseline["assembly_status"]}


def load_baseline(path):
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema_version") != 1 or result.get("units") != "mm" or len(result.get("boards", {})) != 4:
        raise ValueError("unsupported/incomplete mechanical baseline")
    return result


def apply_connector_revision(board_id, board, revision):
    """Keep the original connector pose while checking a documented replacement."""
    if board_id not in revision["applies_to"]:
        raise ValueError(f"connector revision does not apply to {board_id}")
    result = copy.deepcopy(board)
    candidates = [c for c in result["components"] if c["reference"] == revision["reference"]]
    if len(candidates) != 1:
        raise ValueError("connector replacement reference missing/ambiguous in baseline")
    component = candidates[0]
    pose = [component["angle_deg"], *component["at_mm"]]
    component["source_footprint"] = revision["footprint_library_id"]
    component["source_height_mm"] = revision["height_mm"]
    component["pads"] = [dict(pad, at_mm=transform(pad["at_mm"], pose),
                              angle_deg=(pad["angle_deg"] + pose[0]) % 360,
                              copper=component["side"], drill_mm=None, plated=None)
                         for pad in revision["local_pads"]]
    return result


def apply_interface_revision(board_id, board, revision, connector_revisions, component_revisions=None):
    """Apply only the explicit, board-specific RevB geometry exceptions."""
    if board_id not in revision["boards"]:
        raise ValueError(f"interface revision does not apply to {board_id}")
    edits = revision["boards"][board_id]
    result = apply_connector_revision(board_id, board, connector_revisions[revision["connector_revision"]])
    for ref, name in edits.get("component_replacements", {}).items():
        replacement = (component_revisions or {})[name]
        matches = [c for c in result["components"] if c["reference"] == ref]
        if len(matches) != 1:
            raise ValueError(f"replacement component {ref} missing/ambiguous")
        component = matches[0]
        component["at_mm"] = [x + y for x, y in zip(component["at_mm"], replacement["origin_offset_mm"])]
        component["angle_deg"] += replacement["angle_offset_deg"]
        component["source_footprint"] = replacement["footprint_library_id"]
        component["locked"] = replacement.get("locked", component["locked"])
        pose = [component["angle_deg"], *component["at_mm"]]
        component["pads"] = [dict(pad, at_mm=transform(pad["at_mm"], pose),
                                  angle_deg=(pad["angle_deg"] + pose[0]) % 360)
                             for pad in replacement["local_pads"]]
    for ref, delta in edits.get("component_offsets_mm", {}).items():
        matches = [c for c in result["components"] if c["reference"] == ref]
        if len(matches) != 1:
            raise ValueError(f"revision component {ref} missing/ambiguous")
        component = matches[0]
        component["at_mm"] = [x + y for x, y in zip(component["at_mm"], delta)]
        for pad in component["pads"]:
            pad["at_mm"] = [x + y for x, y in zip(pad["at_mm"], delta)]
    for change in edits.get("pad_changes", []):
        components = [c for c in result["components"] if c["reference"] == change["reference"]]
        if len(components) != 1:
            raise ValueError("revision pad component missing/ambiguous")
        pads = [p for p in components[0]["pads"] if p["number"] == change["from_number"]]
        if len(pads) != change["count"] or any(not p["drill_mm"] for p in pads):
            raise ValueError("revision mechanical hole selection differs from baseline")
        for pad in pads:
            pad["number"] = change["to_number"]
            pad["plated"] = change["plated"]
    result["components"].extend(copy.deepcopy(edits.get("required_components", [])))
    result["thermal_vias"] = copy.deepcopy(edits.get("thermal_vias", []))
    result["placement_constraints"] = copy.deepcopy(edits.get("placement_constraints", []))
    result["layer_rules"] = copy.deepcopy(edits.get("layer_rules"))
    result["assembly_status"] = revision["assembly_status"]
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", type=pathlib.Path, default=HERE / "baseline.json")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("summary", help="list recorded interfaces and limitations")
    sources = sub.add_parser("sources", help="verify frozen source PCB SHA256 hashes")
    sources.add_argument("--root", type=pathlib.Path, default=HERE.parents[1])
    check = sub.add_parser("check", help="compare one KiCad PCB with an original board")
    check.add_argument("board_id")
    check.add_argument("pcb", type=pathlib.Path)
    check.add_argument("--tolerance", type=float, default=0.025, help="XY/size tolerance, mm (default .025)")
    check.add_argument("--thickness-tolerance", type=float, default=0.1, help="thickness tolerance, mm (default .1)")
    check.add_argument("--map-ref", action="append", default=[], metavar="OLD=NEW")
    check.add_argument("--connector-revision", choices=["legacy", "fh12"], default="legacy",
                       help="explicitly check the documented CON1 replacement (default: historical legacy)")
    check.add_argument("--revision", choices=["legacy", "naive-revb"], default="legacy",
                       help="explicit RevB interfaces, thermal geometry, placements and candidate stack; historical sources stay frozen")
    check.add_argument("--json", action="store_true", help="emit machine-readable result")
    args = parser.parse_args(argv)
    try:
        baseline = load_baseline(args.baseline)
        if args.command == "sources":
            problems = []
            for name, board in baseline["boards"].items():
                path = args.root / board["source"]["path"]
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != board["source"]["sha256"]:
                    problems.append(f"{name}: source SHA256 changed")
            print("\n".join(problems) if problems else "PASS: all four original PCB source hashes match")
            return bool(problems)
        if args.command == "check":
            if args.board_id not in baseline["boards"]:
                raise ValueError(f"unknown board_id; choose {', '.join(baseline['boards'])}")
            if not 0 < args.tolerance <= 0.1 or not 0 <= args.thickness_tolerance <= 0.2:
                raise ValueError("geometry tolerance must be (0, .1]mm; thickness tolerance [0, .2]mm")
            refs = {}
            for item in args.map_ref:
                old, sep, new = item.partition("=")
                if not sep or not old or not new or old in refs:
                    raise ValueError("--map-ref requires distinct OLD=NEW pairs")
                refs[old] = new
            expected = baseline["boards"][args.board_id]
            intentional_changes = []
            if args.revision != "legacy":
                if args.connector_revision != "legacy":
                    raise ValueError("choose --revision or --connector-revision, not both")
                revision = baseline["interface_revisions"][args.revision]
                expected = apply_interface_revision(args.board_id, expected, revision, baseline["connector_revisions"],
                                                    baseline.get("component_revisions", {}))
                intentional_changes.extend(revision["reasons"])
            elif args.connector_revision != "legacy":
                revision = baseline["connector_revisions"][args.connector_revision]
                expected = apply_connector_revision(args.board_id, expected, revision)
                intentional_changes.append(revision["reason"])
            result = check_board(expected, read_kicad(args.pcb), args.tolerance,
                                 args.thickness_tolerance, refs)
            result["board_id"], result["limitations"] = args.board_id, baseline["limits"]
            result["connector_revision"] = (baseline["interface_revisions"][args.revision]["connector_revision"]
                                             if args.revision != "legacy" else args.connector_revision)
            result["intentional_changes"] = intentional_changes
            result["interface_revision"] = args.revision
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"{'PASS' if result['passed'] else 'FAIL'}: {args.board_id} mechanical interface comparison")
                for problem in result["problems"]:
                    print(f"  {problem}")
                for change in intentional_changes:
                    print(f"  Intentional change: {change}")
                print(result["assembly_status"])
                print("This is not ERC/DRC, a 3D fit check, or a fabrication/assembly approval.")
            return not result["passed"]
        for name, board in baseline["boards"].items():
            refs = [c["reference"] for c in board["components"] if c["locked"]]
            print(f"{name}: {len(board['outline'])} outline edges; locked {', '.join(refs)}; "
                  f"{len(board['standalone_pads'])} standalone holes/contacts; source stack "
                  f"{board['stackup']['copper_and_dielectric_mm']}mm")
            print(f"  {board['assembly_status']}")
        for limit in baseline["limits"]:
            print(f"  {limit}")
        return 0
    except (OSError, ValueError, KeyError, IndexError, TypeError, ZeroDivisionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
