#!/usr/bin/env python3
"""Build explicitly labelled maximum-package bounding boxes, not exact CAD.

Requires OCP (OpenCascade Python). Run with ``python -B``. This script writes
only the five new STEP assets and their JSON manifest; it never edits a PCB or
footprint. Re-run into a separate --output-dir to compare deterministic hashes.
The dimensions are maximum package dimensions from the cited manufacturer
drawings, measured from the package seating plane. PCB solder stand-off is a
separate assembly assumption and is deliberately not included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import OCP
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt
from OCP.Interface import Interface_Static
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer


ASSETS = [
    {
        "filename": "ESP32-PICO-D4_MaxBody_Bounding_Envelope.step",
        "references": ["U4"],
        "manufacturer": "Espressif",
        "part": "ESP32-PICO-D4",
        "dimensions_mm": [7.1, 7.1, 1.04],
        "source_pdf": "esp32-pico-d4.pdf",
        "source_url": "https://www.espressif.com/sites/default/files/documentation/esp32-pico_series_datasheet_en.pdf",
        "drawing": "ESP32-PICO Series Datasheet v1.5, page55, Figure13",
        "dimension_basis": "D/E maximum7.100mm; A maximum1.040mm. Nominal7.000x7.000x0.940mm.",
        "axis_note": "Square package: X/Y exchange has no effect on this unmarked box. No pin1 mark or individual contacts are modelled.",
    },
    {
        "filename": "TDK_VLS3012HBX_MaxBody_Bounding_Envelope.step",
        "references": ["L1"],
        "manufacturer": "TDK",
        "part": "VLS3012HBX-2R2M-N",
        "dimensions_mm": [3.1, 3.1, 1.2],
        "source_pdf": "vls3012hbx-n.pdf",
        "source_url": "https://product.tdk.com/system/files/dam/doc/product/inductor/inductor/smd/catalog/inductor_commercial_power_vls3012hbx-n_en.pdf",
        "product_page": "https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=VLS3012HBX-2R2M-N",
        "drawing": "VLS3012HBX-N type, Shape & Dimensions, page3 of4,20210921",
        "dimension_basis": "L/W3.0+/-0.1mm; height1.2mm maximum. Tape cavity dimensions are not component dimensions.",
        "axis_note": "Square package: X/Y exchange has no effect. Inductor is not polarised. This box does not reproduce the metal terminal shape.",
    },
    {
        "filename": "TI_DPY0002A_MaxBody_Bounding_Envelope.step",
        "references": ["D2"],
        "manufacturer": "Texas Instruments",
        "part": "TPD1E10B06DPYR / DPY0002A",
        "dimensions_mm": [1.1, 0.7, 0.45],
        "source_pdf": "tpd1e10b06.pdf",
        "source_url": "https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf",
        "drawing": "DPY0002A X1SON2 outline, drawing4224561/C,07/2024",
        "dimension_basis": "A maximum1.1mm; B maximum0.7mm; height0.45mm maximum.",
        "axis_note": "Long axisX. In the custom footprint, contacts1/2 lie at localX=-/+0.35mm. No pin identity is encoded in this symmetric bounding box.",
    },
    {
        "filename": "TI_DSG0008A_MaxBody_Bounding_Envelope.step",
        "references": ["U2"],
        "manufacturer": "Texas Instruments",
        "part": "TPS62162DSGR / DSG0008A",
        "dimensions_mm": [2.1, 2.1, 0.8],
        "source_pdf": "tps62162.pdf",
        "source_url": "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
        "drawing": "DSG0008A WSON8 outline, drawing4218900/E,08/2022",
        "dimension_basis": "A/B maximum2.1mm; height0.8mm maximum. Includes package outline, not PCB lands.",
        "axis_note": "Square package: X/Y exchange has no effect. No exposed-pad geometry, leads or pin1 mark are modelled.",
    },
    {
        "filename": "Diodes_SOT23_MaxBody_Bounding_Envelope.step",
        "references": ["VT1", "VT2"],
        "manufacturer": "Diodes Incorporated",
        "part": "MMBT3904-7-F / SOT23",
        "dimensions_mm": [3.0, 2.5, 1.1],
        "source_pdf": "mmbt3904.pdf",
        "source_url": "https://www.diodes.com/assets/Datasheets/MMBT3904.pdf",
        "drawing": "DS30036 Rev27-2,March2025,page6,Package Outline Dimensions",
        "dimension_basis": "H maximum3.00mm; overall lead spanC maximum2.50mm; overall heightK1 maximum1.10mm. The plastic body widthB alone is1.40mm maximum.",
        "axis_note": "Long package axisX; overall lead spanY. Matches custom footprint local contacts1(-0.95,+1),2(+0.95,+1),3(0,-1). The box is symmetric and has no pin1/2/3 marker. A pin-shaped generic SOT23 model would need a separate two-lead/one-lead side alignment check.",
    },
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_step(path: Path, dimensions: list[float]) -> dict:
    reader = STEPControl_Reader()
    if int(reader.ReadFile(str(path))) != 1:
        raise RuntimeError(f"Cannot re-read STEP: {path.name}")
    reader.TransferRoots()
    shape = reader.OneShape()
    if not BRepCheck_Analyzer(shape).IsValid():
        raise RuntimeError(f"Invalid STEP solid: {path.name}")
    bounds = Bnd_Box()
    BRepBndLib.Add_s(shape, bounds)
    lo, hi = bounds.CornerMin(), bounds.CornerMax()
    actual = [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]
    x, y, z = dimensions
    wanted = [-x / 2, -y / 2, 0, x / 2, y / 2, z]
    if any(abs(a - b) > 0.000002 for a, b in zip(actual, wanted)):
        raise RuntimeError(f"Wrong STEP bounds: {path.name}: {actual}")
    solids = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solids += 1
        explorer.Next()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    if solids != 1 or abs(props.Mass() - x * y * z) > 0.000001:
        raise RuntimeError(f"Wrong STEP topology/volume: {path.name}")
    return {
        "valid": True,
        "solid_count": solids,
        "readback_bbox_mm": actual,
        "readback_volume_mm3": props.Mass(),
        "dimension_tolerance_mm": 0.000002,
    }


def make_step(path: Path, dimensions: list[float]) -> dict:
    x, y, z = dimensions
    shape = BRepPrimAPI_MakeBox(gp_Pnt(-x / 2, -y / 2, 0), x, y, z).Shape()
    assert BRepCheck_Analyzer(shape).IsValid()
    # Initialise STEP parameters before setting them, including on the first
    # asset in a fresh process, so even its internal product name is explicit.
    writer = STEPControl_Writer()
    Interface_Static.SetCVal_s("write.step.schema", "AP214IS")
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    Interface_Static.SetCVal_s("write.step.product.name", path.stem)
    if int(writer.Transfer(shape, STEPControl_AsIs)) != 1 or int(writer.Write(str(path))) != 1:
        raise RuntimeError(f"STEP export failed: {path.name}")
    # The OCP writer inserts wall-clock time in FILE_NAME. Normalise only the
    # header, not geometry, for byte-reproducible assets on the same OCP version.
    text = path.read_text()
    text, count = re.subn(
        r"FILE_NAME\(.*?\);",
        "FILE_NAME('" + path.name + "','2026-10-29T00:00:00',"
        "('HoloCubic RevB engineering'),('Maximum bounding envelope - not exact manufacturer CAD'),"
        "'OpenCascade','OpenCascade','');",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("Expected one STEP FILE_NAME header")
    path.write_text(text)
    return inspect_step(path, dimensions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--evidence-dir", type=Path, help="Optional directory of the cited PDF snapshots; only SHA256 and filename are stored")
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for item in ASSETS:
        path = out / item["filename"]
        validation = make_step(path, item["dimensions_mm"])
        entry = dict(item)
        entry["sha256"] = digest(path)
        entry["validation"] = validation
        if args.evidence_dir and (args.evidence_dir / item["source_pdf"]).is_file():
            entry["source_pdf_sha256"] = digest(args.evidence_dir / item["source_pdf"])
        else:
            entry["source_pdf_sha256"] = None
            entry["source_snapshot_status"] = "No local PDF snapshot supplied; source URL and dimension basis are recorded. A null hash is not evidence of a downloaded or verified local file."
        entries.append(entry)
    manifest = {
        "classification": "Maximum-package bounding envelopes; NOT exact manufacturer CAD",
        "units": "millimetres",
        "local_frame": "XY package centre at0,0; seating planeZ=0; Zpositive into package, maximum topheight as specified. Apply the existing KiCad footprint pose; do not double-apply its board rotation.",
        "recommended_model_transform_in_this_project": {"offset_mm": [0, 0, 0], "scale": [1, 1, 1], "rotation_deg": [0, 0, 0]},
        "symmetry": "All boxes are symmetric inX/Y; they do not identify pin1 or polarity. SOT23 long axis isX, matching this project's custom lands.",
        "assembly_limit": "Dimensions exclude PCB solder stand-off, placement/process tolerances beyond the cited package limits, latch operation and mating/insertion clearances. These visual assets are not an assembly-fit or collision certificate.",
        "omitted_details": ["Pins, lead shapes and exposed-pad shape", "Pin1 marks and text", "Chamfers/rounding", "Internal materials and electrical structure"],
        "rebuild": "python -B generate_max_body_envelopes.py --output-dir OUTPUT [--evidence-dir PDF_SNAPSHOTS]. Requires OCP. STEP timestamp is fixed for same-version byte reproducibility.",
        "generator_sha256": digest(Path(__file__)),
        "OCP_version": getattr(OCP, "__version__", "unknown"),
        "assets": entries,
    }
    (out / "max_body_bounding_envelopes.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({e["filename"]: e["sha256"] for e in entries}, indent=2))


if __name__ == "__main__":
    main()
