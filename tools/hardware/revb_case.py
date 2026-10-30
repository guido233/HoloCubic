#!/usr/bin/env python3
"""Reproduce the Naive RevB lower-shell internal relief from frozen CAD.

Optional CAD runtime: Python 3.11+ and ``cadquery-ocp==8.0.1.1.0``.
The normal mechanical baseline checker remains standard-library only.

Run from the repository root::

    python tools/hardware/revb_case.py --output /tmp/Naive-RevB-Mechanical

Reads the original STEP and current PCB; writes only to a new output directory.
The transform is a documented nominal seat reconstruction, not an assembly mate
or physical fit approval. All geometry/clearance budgets are in baseline.json.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import pathlib
import sys

import mechanical_baseline as mechanical


def run(args):
    if args.output.exists():
        raise ValueError("output directory already exists; choose a new directory")
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut
        from OCP.BRepBndLib import BRepBndLib
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        from OCP.BRepGProp import BRepGProp
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.GProp import GProp_GProps
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
        from OCP.gp import gp_Pnt, gp_Trsf
    except ImportError as error:
        raise ValueError("CAD runtime missing; install cadquery-ocp==8.0.1.1.0 in a separate venv") from error

    baseline = mechanical.load_baseline(args.baseline)
    spec = baseline["case_revisions"]["naive-revb-bottom-relief"]
    if spec["xy_clearance_mm"] < 0.25 or spec["z_clearance_mm"] < 0.15:
        raise ValueError("case relief requires at least 0.25 mm XY and 0.15 mm Z clearance")
    for source in spec["sources"]:
        path = args.root / source["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"frozen case source SHA256 changed: {path}")
    pcb_path = getattr(args, "pcb", None) or args.root / spec["pcb_path"]
    current = mechanical.read_kicad(pcb_path)
    revision = baseline["interface_revisions"]["naive-revb"]
    expected = mechanical.apply_interface_revision("Naive_MainBoard", baseline["boards"]["Naive_MainBoard"],
                                                   revision, baseline["connector_revisions"],
                                                   baseline["component_revisions"])
    comparison = mechanical.check_board(expected, current)
    if not comparison["passed"]:
        raise ValueError("current MainBoard does not match the reviewed interface profile: " +
                         "; ".join(comparison["problems"]))
    low, high = spec["finished_board_range_for_USB_mm"]
    if not low <= current["thickness_mm"] <= high:
        raise ValueError("current PCB thickness is outside the reviewed USB/case range")
    for part in spec["parts"]:
        actual = current["components"].get(part["reference"])
        if (not actual or actual["side"] != part["side"] or
                math.dist(actual["at_mm"], part["center_mm"]) > 0.005 or
                mechanical.angle_error(actual["angle_deg"], -part["angle_deg"], 180) > 0.1):
            raise ValueError(f"unreviewed B-component pose: {part['reference']}")
        corners = []
        for pad in actual["pads"]:
            w, h = [x / 2 for x in pad["size_mm"]]
            corners.extend(mechanical.transform([a, b], [pad["angle_deg"], *pad["at_mm"]])
                           for a, b in ((-w, -h), (-w, h), (w, -h), (w, h)))
        lands = [min(p[0] for p in corners) - part["center_mm"][0],
                 min(p[1] for p in corners) - part["center_mm"][1],
                 max(p[0] for p in corners) - part["center_mm"][0],
                 max(p[1] for p in corners) - part["center_mm"][1]]
        if max(abs(a - b) for a, b in zip(lands, part["land_bbox_relative_mm"])) > 0.005:
            raise ValueError(f"unreviewed B-component solder-land envelope: {part['reference']}")
    for feature in spec.get("penetrating_features", []):
        parent = current["components"].get(feature["parent_reference"], {})
        pads = [p for p in parent.get("pads", []) if p["number"] == feature["pad_number"] and
                math.dist(p["at_mm"], feature["center_mm"]) <= 0.005 and p["copper"] == "*.Cu"]
        if len(pads) != 1:
            raise ValueError(f"unreviewed penetrating pad: {feature['reference']}")
        budget = spec["usb_stake_budget"]
        intrusion = budget["nominal_length_mm"] + budget["length_tolerance_mm"] - low
        if feature["body_maximum_mm"][2] < intrusion - 1e-6:
            raise ValueError("USB stake relief does not cover minimum board/maximum stake")

    def read_step(path):
        reader = STEPControl_Reader()
        if reader.ReadFile(str(path)) != IFSelect_RetDone or not reader.TransferRoots():
            raise ValueError(f"cannot read STEP: {path}")
        return reader.OneShape()

    def volume(shape):
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, props)
        return props.Mass()

    def common_volume(a, b):
        operation = BRepAlgoAPI_Common(a, b)
        if not operation.IsDone():
            raise ValueError("CAD common operation failed")
        return volume(operation.Shape())

    def distance(a, b):
        operation = BRepExtrema_DistShapeShape(a, b)
        operation.Perform()
        if not operation.IsDone():
            raise ValueError("CAD distance operation failed")
        return operation.Value()

    def bounds(shape):
        box = Bnd_Box()
        BRepBndLib.AddOptimal_s(shape, box, False, False)
        lo, hi = box.CornerMin(), box.CornerMax()
        return [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]

    def solid_count(shape):
        explorer, count = TopExp_Explorer(shape, TopAbs_SOLID), 0
        while explorer.More():
            count += 1
            explorer.Next()
        return count

    transform = gp_Trsf()
    transform.SetValues(*spec["board_to_case_transform_3x4"])

    def to_case(shape):
        return BRepBuilderAPI_Transform(shape, transform, True).Shape()

    def component_box(part, xy_margin=0, extra_depth=0, above_seat=0, include_lands=False):
        width, depth, height = part["body_maximum_mm"]
        x, y = part["center_mm"]
        height += part.get("solder_height_budget_mm", spec["solder_standoff_budget_mm"])
        x0, y0, x1, y1 = -width / 2, -depth / 2, width / 2, depth / 2
        if include_lands:
            land = part["land_bbox_relative_mm"]
            x0, y0, x1, y1 = min(x0, land[0]), min(y0, land[1]), max(x1, land[2]), max(y1, land[3])
        shape = BRepPrimAPI_MakeBox(gp_Pnt(x + x0 - xy_margin, y + y0 - xy_margin, -above_seat),
                                    x1 - x0 + 2 * xy_margin, y1 - y0 + 2 * xy_margin,
                                    height + extra_depth + above_seat).Shape()
        return to_case(shape)

    original = read_step(args.root / spec["sources"][0]["path"])
    upper = read_step(args.root / spec["sources"][1]["path"])
    if not BRepCheck_Analyzer(original).IsValid() or solid_count(original) != 1:
        raise ValueError("original lower shell is not one valid solid")
    revised, rows = original, []
    envelopes = spec["parts"] + spec.get("penetrating_features", [])
    for part in envelopes:
        body = component_box(part)
        tool = component_box(part, spec["xy_clearance_mm"], spec["z_clearance_mm"],
                             spec["cut_above_seat_mm"], include_lands=True)
        cut = BRepAlgoAPI_Cut(revised, tool)
        if not cut.IsDone():
            raise ValueError(f"CAD relief cut failed: {part['reference']}")
        revised = cut.Shape()
        rows.append({"reference": part["reference"], "maximum_body_with_solder_budget_case_bbox_mm": bounds(body),
                     "cut_bbox_case_mm": bounds(tool), "original_intersection_mm3": common_volume(original, body),
                     "upper_intersection_mm3": common_volume(upper, body)})

    if not BRepCheck_Analyzer(revised).IsValid() or solid_count(revised) != 1:
        raise ValueError("revised lower shell is not one valid solid")
    for row, part in zip(rows, envelopes):
        body = component_box(part)
        row["revised_intersection_mm3"] = common_volume(revised, body)
        row["revised_minimum_clearance_mm"] = distance(revised, body)
        if row["revised_intersection_mm3"] > 1e-8 or row["revised_minimum_clearance_mm"] < spec["z_clearance_mm"] - 1e-5:
            raise ValueError(f"relief clearance failed: {part['reference']}")
    original_bounds, revised_bounds = bounds(original), bounds(revised)
    if max(abs(a - b) for a, b in zip(original_bounds, revised_bounds)) > 1e-5:
        raise ValueError("shell outer bounds changed")
    original_volume, revised_volume = volume(original), volume(revised)
    if not original_volume > revised_volume > 0:
        raise ValueError("unexpected shell volume after cuts")
    newly_lowered_floor = min(row["cut_bbox_case_mm"][2] for row in rows) - spec["case_outer_floor_z_mm"]
    side_wall = min(min(row["cut_bbox_case_mm"][0] - spec["case_outer_x_range_mm"][0],
                        spec["case_outer_x_range_mm"][1] - row["cut_bbox_case_mm"][3]) for row in rows)
    def post_gap(row, center):
        x0, y0, _, x1, y1, _ = row["cut_bbox_case_mm"]
        dx, dy = max(x0 - center[0], 0, center[0] - x1), max(y0 - center[1], 0, center[1] - y1)
        return math.hypot(dx, dy) - spec["screw_post_keep_radius_mm"]
    post_clearance = min(post_gap(row, center) for row in rows for center in spec["screw_post_centers_case_xy_mm"])
    if newly_lowered_floor < 2 or side_wall < 2 or post_clearance < 1:
        raise ValueError("new relief violates the reviewed floor/sidewall/post budget")

    # Never overwrite the historical STEP or an existing output directory.
    args.output.mkdir(parents=True, exist_ok=False)
    step_path = args.output / "Lower-RevB.step"
    writer = STEPControl_Writer()
    writer.Transfer(revised, STEPControl_AsIs)
    if writer.Write(str(step_path)) != IFSelect_RetDone:
        raise ValueError("cannot write revised STEP")
    reloaded = read_step(step_path)
    # Imported trimmed curves are reparameterized on STEP serialization. Use a
    # one-part-per-million volume budget, plus independent bbox/clearance checks.
    round_trip_volume_delta = abs(volume(reloaded) - revised_volume)
    if (not BRepCheck_Analyzer(reloaded).IsValid() or solid_count(reloaded) != 1 or
            round_trip_volume_delta > max(1e-5, revised_volume * 1e-6) or
            max(abs(a - b) for a, b in zip(bounds(reloaded), revised_bounds)) > 1e-5):
        raise ValueError(f"STEP round-trip verification failed: valid={BRepCheck_Analyzer(reloaded).IsValid()}, "
                         f"solids={solid_count(reloaded)}, volume {revised_volume} -> {volume(reloaded)}")
    for row, part in zip(rows, envelopes):
        body = component_box(part)
        row["STEP_reloaded_intersection_mm3"] = common_volume(reloaded, body)
        row["STEP_reloaded_minimum_clearance_mm"] = distance(reloaded, body)
        if (row["STEP_reloaded_intersection_mm3"] > 1e-8 or
                row["STEP_reloaded_minimum_clearance_mm"] < spec["z_clearance_mm"] - 1e-5):
            raise ValueError(f"STEP round-trip body clearance failed: {part['reference']}")
    try:
        pcb_reference = pcb_path.resolve().relative_to(args.root.resolve()).as_posix()
    except ValueError:
        pcb_reference = str(pcb_path)
    report = {"classification": spec["classification"], "source_CAD": spec["sources"],
              "input_pcb": pcb_reference, "input_pcb_sha256": hashlib.sha256(pcb_path.read_bytes()).hexdigest(),
              "cad_runtime": {"package": "cadquery-ocp", "version": importlib.metadata.version("cadquery-ocp")},
              "script_sha256": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
              "case_parameters_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(),
              "board_to_case_transform_3x4": spec["board_to_case_transform_3x4"],
              "basis": spec["basis"], "xy_clearance_mm": spec["xy_clearance_mm"],
              "z_clearance_mm": spec["z_clearance_mm"], "parts": rows,
              "original_volume_mm3": original_volume, "revised_volume_mm3": revised_volume,
              "STEP_reloaded_volume_mm3": volume(reloaded),
              "removed_volume_mm3": original_volume - revised_volume,
              "original_valid": True, "original_solid_count": 1,
              "revised_valid": True, "revised_solid_count": 1,
              "original_bbox_mm": original_bounds, "revised_bbox_mm": revised_bounds,
              "STEP_reloaded_bbox_mm": bounds(reloaded), "outer_bbox_unchanged": True,
              "minimum_newly_lowered_floor_to_exterior_mm": newly_lowered_floor,
              "original_TF_recess_floor_mm_unchanged": spec["original_TF_recess_floor_z_mm"],
              "minimum_new_cut_to_outer_sidewall_mm": side_wall,
              "minimum_new_cut_to_screw_post_keepout_mm": post_clearance,
              "output_valid_solid_count": 1, "STEP_round_trip_verified": True,
              "STEP_round_trip_volume_delta_mm3": round_trip_volume_delta,
              "STEP_round_trip_relative_volume_tolerance": 1e-6,
              "output_step_sha256": hashlib.sha256(step_path.read_bytes()).hexdigest(),
              "limits": spec["limits"]}
    (args.output / "Lower-RevB-verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {step_path}; valid single solid, STEP round-trip passed")
    print(f"New relief floor >= {newly_lowered_floor:.5f}mm; sidewall >= {side_wall:.5f}mm; "
          f"post keepout clearance >= {post_clearance:.5f}mm")
    print("Nominal CAD result only; assembled seat, case and card access require sample validation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument("--baseline", type=pathlib.Path, default=pathlib.Path(__file__).with_name("baseline.json"))
    parser.add_argument("--pcb", type=pathlib.Path, help="reviewed candidate PCB override; default is the workspace MainBoard")
    parser.add_argument("--output", required=True, type=pathlib.Path, help="new directory; must not already exist")
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
