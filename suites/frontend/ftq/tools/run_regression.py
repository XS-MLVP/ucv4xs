#!/usr/bin/env python3
"""Reproducible FTQ regression with uc-toffee and native coverage evidence.

Run with the uc-toffee virtual environment:

    .venv-uc-toffee/bin/python tools/run_regression.py --output results/ftq-...

The script owns a new result directory, runs pytest from the suite root, then
merges each DUT's raw Verilator database and writes coverage.json plus
coverage-gaps.md.  It never reuses an existing output directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from datetime import timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DUTS = ("resolve_queue", "commit_queue", "ftq")


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("selection", nargs="*", default=["tests"])
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to reuse result directory: {output}")
    output.mkdir(parents=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["FTQ_RESULT_DIR"] = str(output)
    env["PYTHONHASHSEED"] = str(args.seed)
    command = [
        sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
        f"--junitxml={output / 'pytest.xml'}", *args.selection,
    ]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env)
    record = {
        "format": "ftq-regression",
        "version": 1,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "toffee": subprocess.check_output(
            [sys.executable, "-c", "import toffee; print(toffee.__file__)"],
            text=True).strip(),
        "command": command,
        "selection": args.selection,
        "seed": args.seed,
        "pytest_exitstatus": result.returncode,
        "dut_packages": {
            name: {
                "provenance": json.loads((ROOT / "dut" / name / "provenance.json").read_text()),
                "package_sha256": {
                    file.name: digest(file)
                    for file in sorted((ROOT / "dut" / name).iterdir())
                    if file.is_file() and file.suffix in {".so", ".py", ".json", ".yaml"}
                },
            }
            for name in DUTS
        },
        "rtl_sha256": {
            name: {
                file.name: digest(file)
                for file in sorted((ROOT / "rtl" / name).iterdir())
                if file.is_file() and file.suffix in {".sv", ".v"}
            }
            for name in DUTS
        },
    }
    if (output / "pytest.xml").is_file():
        root = ET.parse(output / "pytest.xml").getroot()
        counts = {"tests": 0, "passed": 0, "failures": 0, "errors": 0,
                  "xfail": 0, "xpass": 0, "skipped": 0}
        for case in root.iter("testcase"):
            counts["tests"] += 1
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                if failure.get("message", "").startswith("[XPASS(strict)]"):
                    counts["xpass"] += 1
                else:
                    counts["failures"] += 1
            elif error is not None:
                counts["errors"] += 1
            elif skipped is not None:
                if skipped.get("type") == "pytest.xfail":
                    counts["xfail"] += 1
                else:
                    counts["skipped"] += 1
            else:
                counts["passed"] += 1
        record["tests"] = counts
    (output / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    if result.returncode != 0:
        return result.returncode
    trace = subprocess.run([
        sys.executable, str(ROOT / "tools/traceability.py"),
        "--xml", str(output / "pytest.xml"),
        "--output", str(output / "traceability.md"),
    ], cwd=ROOT)
    if trace.returncode != 0:
        return trace.returncode
    coverage = subprocess.run([
        sys.executable, str(ROOT / "tools/coverage_report.py"),
        "--result-dir", str(output),
        *sum((["--dut", name] for name in DUTS), []),
        "--output", str(output / "coverage-report"),
    ], cwd=ROOT)
    return coverage.returncode


if __name__ == "__main__":
    raise SystemExit(main())
