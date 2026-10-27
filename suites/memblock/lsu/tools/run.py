#!/usr/bin/env python3
"""Run LSU UT through the toffee main-branch runner.

Normal runs never call SetWaveform. Picker's generated top still has a default
``$dumpfile``, so pytest runs from a temporary cwd. No per-cycle signal or
transaction dump is produced, and a fresh output directory is mandatory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = __import__("ucv.runtime", fromlist=["toolchain"]).toolchain()
TOFFEE = list(LOCK["toffee"]["runner_command"])
VERILATOR_COVERAGE = LOCK["verilator"]["coverage_processor"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("tests", nargs="+")
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in (".", ".."):
        raise SystemExit("run name must be one fresh directory name")
    output = (ROOT / "results" / args.name).resolve()
    if output.exists():
        raise SystemExit(f"output already exists: {output}")
    removed = []
    for name in ("memory-direct.fst", "memory-direct.vcd"):
        stale = ROOT / name
        if stale.exists():
            removed.append({"path": str(stale), "bytes": stale.stat().st_size})
            stale.unlink()
    command = [
        *TOFFEE, *[str((ROOT / path).resolve()) for path in args.tests],
        "--workers", str(args.workers),
        "--output", str(output),
        "--export-coverage-json",
        "--native-coverage-tool", VERILATOR_COVERAGE,
    ]
    with tempfile.TemporaryDirectory(prefix="lsu-run-", dir=None) as temp:
        # Keep failed node names and tracebacks, not just a manifest FAIL count.
        # Stage outside output: toffee requires a fresh output directory.
        console_path = Path(temp) / "console.log"
        junit_path = Path(temp) / "junit.xml"
        env = dict(os.environ)
        env["PYTEST_ADDOPTS"] = (env.get("PYTEST_ADDOPTS", "") +
                                  " --junitxml=" + str(junit_path)).strip()
        with console_path.open("w") as console:
            proc = subprocess.Popen(command, cwd=temp, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1)
            assert proc.stdout is not None
            for line in proc.stdout:
                console.write(line)
                sys.stdout.write(line)
                sys.stdout.flush()
            proc.wait()
        output.mkdir(parents=True, exist_ok=True)
        (output / "console.log").write_bytes(console_path.read_bytes())
        if junit_path.is_file():
            (output / "junit.xml").write_bytes(junit_path.read_bytes())
        fingerprint = {}
        for directory in ("tests", "lsuverify", "tools"):
            for source in sorted((ROOT / directory).rglob("*.py")):
                fingerprint[str(source.relative_to(ROOT))] = hashlib.sha256(
                    source.read_bytes()).hexdigest()
        for relative in ("conftest.py", "pytest.ini", "manifest/toolchain.json",
                         "manifest/lsu-rtl.sha256"):
            source = ROOT / relative
            fingerprint[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        for requested in args.tests:
            path = ROOT / requested
            sources = [path] if path.is_file() else sorted(path.rglob("*.py"))
            for source in sources:
                fingerprint[str(source.relative_to(ROOT))] = hashlib.sha256(
                    source.read_bytes()).hexdigest()
        (output / "run-provenance.json").write_text(json.dumps({
            "schema_version": 1, "command": command,
            "verilator_seed": int(os.environ.get("LSU_VERILATOR_SEED", "1")),
            "sources_sha256": fingerprint,
            "console_sha256": hashlib.sha256(console_path.read_bytes()).hexdigest(),
            "returncode": proc.returncode,
        }, indent=2) + "\n")
        for name in ("memory-direct.fst", "memory-direct.vcd"):
            stray = Path(temp) / name
            if stray.exists():
                stray.unlink()
    stray_project = [str(p) for p in (ROOT / "memory-direct.fst", ROOT / "memory-direct.vcd") if p.exists()]
    stray_run = [str(p) for p in output.rglob("*")
                 if p.is_file() and p.suffix in (".fst", ".vcd")]
    per_cycle = [str(p) for p in output.rglob("*.jsonl")]
    per_cycle += [str(p) for p in output.rglob("*trace*.json")]
    policy = {
        "schema_version": 1,
        "format": "lsu-trace-policy-v1",
        "picker_trace_compiled": True,
        "picker_coverage_compiled": True,
        "runtime_set_waveform": False,
        "per_cycle_signal_dump": False,
        "per_cycle_transaction_dump": False,
        "debug_trace_requested": False,
        "toffee_keep_coverage_inputs": False,
        "runtime_default_dumpfile_cwd": "temporary directory outside the project",
        "kept_waveforms_in_run": bool(stray_run),
        "stray_waveforms_in_project": stray_project,
        "removed_stale_project_waveforms": removed,
        "stray_waveforms_in_run": stray_run,
        "per_cycle_files": per_cycle,
        "status": "PASS" if not stray_project and not stray_run and not per_cycle else "FAIL",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "trace-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    print(f"trace policy: {policy['status']}; evidence: {output}")
    raise SystemExit(proc.returncode if policy["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
