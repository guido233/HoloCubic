#!/usr/bin/env python3
"""Test production networking without hardware, credentials, or outgoing requests.

Pass the ArduinoJson 7.4.3 src directory, or install the project's PIO dependencies:
    python3 test/network_test/run_host_tests.py /path/to/ArduinoJson/src
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
candidates = [Path(sys.argv[1])] if len(sys.argv) > 1 else list(
    (PROJECT / ".pio/libdeps").glob("*/ArduinoJson/src")
)
json_include = next((p for p in candidates if (p / "ArduinoJson.h").is_file()), None)
if json_include is None:
    sys.exit("Install the PIO dependencies first, or pass ArduinoJson's src directory.")
compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
if not compiler:
    sys.exit("A host C++ compiler is required.")
with tempfile.TemporaryDirectory(prefix="holocubic-network-test-") as temporary:
    for bundle in (1, 0):
        executable = Path(temporary) / f"network-{bundle}"
        command = [compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-function", f"-DTEST_CERTIFICATE_BUNDLE={bundle}",
                   f"-I{HERE / 'stubs'}", f"-I{PROJECT / 'include'}", f"-I{json_include}",
                   str(PROJECT / "src/holo_network.cpp"), str(HERE / "network_test.cpp"),
                   "-o", str(executable)]
        subprocess.run(command, check=True)
        subprocess.run([str(executable)], check=True)
