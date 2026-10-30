"""Regression checks against the actual native boards and generated case artifact.

Standard library only. Before a reviewed candidate is adopted into the workspace,
HOLOCUBIC_MECHANICAL_MAIN may explicitly select its native PCB for these tests.
These checks do not replace native DRC, CAD regeneration or a physical assembly.
"""

import copy
import hashlib
import json
import os
import pathlib
import unittest

import mechanical_baseline as mechanical

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAIVE = ROOT / "1.Hardware/RevB-KiCad/Naive"


class MechanicalRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = mechanical.load_baseline(ROOT / "tools/hardware/baseline.json")
        revision = cls.baseline["interface_revisions"]["naive-revb"]
        cls.expected = mechanical.apply_interface_revision(
            "Naive_MainBoard", cls.baseline["boards"]["Naive_MainBoard"], revision,
            cls.baseline["connector_revisions"], cls.baseline["component_revisions"])
        path = pathlib.Path(os.environ.get("HOLOCUBIC_MECHANICAL_MAIN", NAIVE / "MainBoard/MainBoard.kicad_pcb"))
        cls.current = mechanical.read_kicad(path)

    def assert_rejected(self, changes):
        for label, change in changes:
            with self.subTest(label=label):
                board = copy.deepcopy(self.current)
                change(board)
                result = mechanical.check_board(self.expected, board)
                self.assertFalse(result["passed"], f"unsafe change accepted: {label}")

    def test_actual_main_and_extend_interfaces(self):
        result = mechanical.check_board(self.expected, self.current)
        self.assertTrue(result["passed"], result["problems"])
        expected = mechanical.apply_interface_revision(
            "Naive_ExtendBoard", self.baseline["boards"]["Naive_ExtendBoard"],
            self.baseline["interface_revisions"]["naive-revb"],
            self.baseline["connector_revisions"], self.baseline["component_revisions"])
        current = mechanical.read_kicad(NAIVE / "ExtendBoard/ExtendBoard.kicad_pcb")
        result = mechanical.check_board(expected, current, references={"1": "LCD1"})
        self.assertTrue(result["passed"], result["problems"])

    def test_layer_plane_keepout_and_case_placement_faults(self):
        def inner(board):
            return next(z for z in board["zones"]
                        if set(z["layers"]) == {"In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu"})

        self.assert_rejected([
            ("unreviewed two-layer board", lambda b: b.update(copper_layers=["F.Cu", "B.Cu"])),
            ("obsolete four-layer candidate", lambda b: b.update(copper_layers=["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])),
            ("core thickness", lambda b: next(x for x in b["stackup"] if x["name"] == "dielectric 2").update(thickness_mm=.8)),
            ("nominal total thickness", lambda b: b.update(thickness_mm=1.09112)),
            ("RF feed keepout removed", lambda b: b["zones"].remove(next(z for z in b["zones"]
                if set(z["layers"]) == {"In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu"} and len(z["polygons"][0]) == 4))),
            ("inner antenna vias allowed", lambda b: inner(b)["keepout"].update(vias="allowed")),
            ("L2 plane removed", lambda b: b["zones"].remove(next(z for z in b["zones"]
                if z["layers"] == ["In1.Cu"] and not z["keepout"]))),
            ("signal route splits L2 intent", lambda b: b["copper_tracks"].append({"layer": "In1.Cu", "net_hint": "GPIO5"})),
            ("L5 plane removed", lambda b: b["zones"].remove(next(z for z in b["zones"]
                if z["layers"] == ["In4.Cu"] and not z["keepout"]))),
            ("signal route splits L5 intent", lambda b: b["copper_tracks"].append({"layer": "In4.Cu", "net_hint": "GPIO5"})),
            ("obsolete resistor pack", lambda b: b["components"]["R7"].update(at_mm=[150, 94.2])),
            ("obsolete R16 bank position", lambda b: b["components"]["R16"].update(at_mm=[147.7, 97.2])),
            ("obsolete distant CT capacitor", lambda b: b["components"]["C16"].update(at_mm=[149.22, 98.04])),
        ])

    def test_thermal_land_stencil_and_via_faults(self):
        def ep(board):
            return next(p for p in board["components"]["U4"]["pads"] if p["number"] == "0")

        def paste(board):
            return next(p for p in board["components"]["U4"]["pads"] if not p["number"])

        def via(board):
            return min(board["vias"], key=lambda v: (v["at_mm"][0] - 151.4475) ** 2 +
                       (v["at_mm"][1] - 112.2045) ** 2)

        self.assert_rejected([
            ("old undersize EP", lambda b: ep(b).update(size_mm=[4.064, 4.064])),
            ("EP mask opening", lambda b: ep(b).update(solder_mask_margin_mm=0)),
            ("full paste restored", lambda b: ep(b)["layers"].append("F.Paste")),
            ("pin1 chamfer removed", lambda b: ep(b).update(chamfer_corners=[])),
            ("oversize paste window", lambda b: paste(b).update(size_mm=[1, 1])),
            ("paste becomes copper", lambda b: paste(b)["layers"].append("F.Cu")),
            ("thermal drill", lambda b: via(b).update(drill_mm=.35)),
            ("thermal wrong net", lambda b: via(b).update(net_hint="3V3")),
            ("thermal back tenting", lambda b: via(b)["tenting"].update(back="no")),
            ("signal land moved", lambda b: next(p for p in b["components"]["U4"]["pads"]
                if p["number"] == "1")["at_mm"].__setitem__(0, 148.8)),
        ])

    def test_whole_board_rotation_preserves_interfaces_and_keepouts(self):
        board, pose = copy.deepcopy(self.current), [37, 5, -12]
        for component in board["components"].values():
            component["at_mm"] = mechanical.transform(component["at_mm"], pose)
            component["angle_deg"] += pose[0]
        for pad in board["pads"]:
            pad["at_mm"] = mechanical.transform(pad["at_mm"], pose)
            pad["angle_deg"] += pose[0]
        for via in board["vias"]:
            via["at_mm"] = mechanical.transform(via["at_mm"], pose)
        for edge in board["outline"]:
            for key in ("start_mm", "mid_mm", "end_mm"):
                if key in edge:
                    edge[key] = mechanical.transform(edge[key], pose)
        for zone in board["zones"]:
            zone["polygons"] = [[mechanical.transform(p, pose) for p in polygon]
                                for polygon in zone["polygons"]]
        result = mechanical.check_board(self.expected, board)
        self.assertTrue(result["passed"], result["problems"])

    def test_original_altium_sources_remain_frozen(self):
        for name, board in self.baseline["boards"].items():
            with self.subTest(board=name):
                data = (ROOT / board["source"]["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), board["source"]["sha256"])

    def test_display_long_manual_windows_and_connector_revision(self):
        expected = mechanical.apply_interface_revision(
            "Naive_ExtendBoard", self.baseline["boards"]["Naive_ExtendBoard"],
            self.baseline["interface_revisions"]["naive-revb"],
            self.baseline["connector_revisions"], self.baseline["component_revisions"])
        current = mechanical.read_kicad(NAIVE / "ExtendBoard/ExtendBoard.kicad_pcb")

        def old_window(board):
            for pad in board["components"]["LCD1"]["pads"]:
                pad["at_mm"] = [156.21, 111.7219 - .7 * (int(pad["number"]) - 1)]
                pad["size_mm"] = [.4, 2.032]
                pad["roundrect_ratio"] = .25

        changes = [
            ("obsolete short LCD window", old_window),
            ("obsolete FFC origin", lambda b: b["components"]["CON1"].update(at_mm=[149.8346, 105.0417])),
            ("LCD paste restored", lambda b: b["components"]["LCD1"]["pads"][0]["layers"].append("F.Paste")),
            ("LCD mask expansion", lambda b: b["components"]["LCD1"]["pads"][0].update(solder_mask_margin_mm=.05)),
        ]
        for label, change in changes:
            with self.subTest(label=label):
                board = copy.deepcopy(current)
                change(board)
                result = mechanical.check_board(expected, board, references={"1": "LCD1"})
                self.assertFalse(result["passed"], f"unreviewed display change accepted: {label}")

    def test_generated_case_artifact_matches_reviewed_parameters(self):
        report = json.loads((NAIVE / "Mechanical/Lower-RevB-verification.json").read_text())
        step = (NAIVE / "Mechanical/Lower-RevB.step").read_bytes()
        parameters = self.baseline["case_revisions"]["naive-revb-bottom-relief"]
        self.assertEqual(hashlib.sha256(step).hexdigest(), report["output_step_sha256"])
        self.assertEqual(hashlib.sha256((ROOT / "tools/hardware/revb_case.py").read_bytes()).hexdigest(), report["script_sha256"])
        self.assertEqual(hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest(), report["case_parameters_sha256"])
        for source in report["source_CAD"]:
            self.assertEqual(hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest(), source["sha256"])


if __name__ == "__main__":
    unittest.main()
