#!/usr/bin/env python3
"""Render the production GUI with managed LVGL on the host, without Arduino hardware."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    test_dir = Path(__file__).resolve().parent
    firmware_dir = test_dir.parent.parent
    dependency_dir = firmware_dir / ".pio/libdeps"
    preferred = dependency_dir / "naive/lvgl"
    candidates = [preferred] if (preferred / "lvgl.h").is_file() else sorted(dependency_dir.glob("*/lvgl"))
    lvgl_dir = None
    for candidate in candidates:
        manifest_path = candidate / "library.json"
        if (candidate / "lvgl.h").is_file() and manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("version") == "9.6.0":
                lvgl_dir = candidate
                break
    if lvgl_dir is None:
        raise SystemExit("Install the project's pinned dependencies with pio pkg install first.")
    tft_dir = lvgl_dir.parent / "TFT_eSPI"
    if not (tft_dir / "TFT_Drivers/ST7789_Rotation.h").is_file():
        raise SystemExit("Install the project's pinned TFT_eSPI dependency with pio pkg install first.")
    print(f"Using LVGL 9.6.0 from {lvgl_dir}", flush=True)
    sources = sorted((lvgl_dir / "src").rglob("*.c"))
    application_sources = [firmware_dir / "src" / name for name in (
        "lv_port_indev.c", "lv_cubic_gui.c", "gui_guider.c", "setup_scr_home.c",
        "setup_scr_scenes.c", "events_init.c", "lv_font_simsun_12.c",
    )]
    application_sources.append(firmware_dir / "src/display.cpp")
    sources.extend(application_sources + [test_dir / "test.c", test_dir / "test_display.cpp"])
    compiler = os.environ.get("CC", "cc")
    cpp_compiler = os.environ.get("CXX", "c++")
    flags = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
             "-DLV_CONF_INCLUDE_SIMPLE", f"-I{test_dir / 'stubs'}", f"-I{firmware_dir / 'include'}",
             f"-I{lvgl_dir}", f"-I{tft_dir}"]

    with tempfile.TemporaryDirectory(prefix="holocubic-gui-test-") as build_dir:
        def compile_source(item):
            index, source = item
            output = str(Path(build_dir) / f"{index}.o")
            checks = ["-Wall", "-Wextra", "-Werror"] if source in application_sources or source.parent == test_dir else []
            cpp = source.suffix == ".cpp"
            command = [cpp_compiler, "-std=c++17"] if cpp else [compiler, "-std=c11"]
            subprocess.run([*command, *flags, *checks, "-c", str(source), "-o", output], check=True)
            return output

        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
            objects = list(pool.map(compile_source, enumerate(sources)))
        executable = str(Path(build_dir) / "gui_test")
        subprocess.run([cpp_compiler, *flags, *objects, "-lm", "-o", executable], check=True)
        subprocess.run([executable], check=True)


if __name__ == "__main__":
    main()
