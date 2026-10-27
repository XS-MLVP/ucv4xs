#!/usr/bin/env python3
"""Run the TLBFA UT through the toffee main-branch runner.

Policy:
- the DUT is a Picker memory-direct build with trace and coverage compiled in;
- normal runs do not call SetWaveform and execute from a temporary working
  directory, so Picker's generated ``$dumpfile("memory-direct.fst")`` never
  lands in the evidence tree;
- waveforms are not offered as a runtime option: the trace capability is only
  compiled, never enabled.

A fresh run name is required; results are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = __import__("ucv.runtime", fromlist=["toolchain"]).toolchain()
TOFFEE = shlex.split(LOCK["toffee"]["runner_command"])
VERILATOR_COVERAGE = LOCK["verilator"]["coverage_processor"]


def verification_sources():
    paths = [path for folder in ("tests", "mmuverify", "tools")
             for path in (ROOT / folder).rglob("*.py")]
    paths += [ROOT / name for name in ("conftest.py", "pytest.ini",
              "manifest/toolchain.json", "manifest/pma-reset-reference.json")]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("tests", nargs="+", help="test paths, relative to this project")
    args = parser.parse_args()
    if Path(args.name).name != args.name or args.name in (".", ".."):
        raise SystemExit("run name must be one fresh directory name")
    output = (ROOT / "results" / args.name).resolve()
    if output.exists():
        raise SystemExit(f"output already exists: {output}")
    before_sources = verification_sources()
    removed_stale = []
    for name in ("memory-direct.fst", "memory-direct.vcd"):
        stale = ROOT / name
        if stale.exists():
            removed_stale.append({"path": str(stale), "bytes": stale.stat().st_size})
            stale.unlink()

    command = [
        *TOFFEE, *[str((ROOT / path).resolve()) for path in args.tests],
        "--workers", str(args.workers),
        "--output", str(output),
        "--export-coverage-json",
        "--native-coverage-tool", VERILATOR_COVERAGE,
    ]

    with tempfile.TemporaryDirectory(prefix="mmu-run-", dir=None) as temp:
        proc = subprocess.run(command, cwd=temp, env=dict(os.environ), timeout=1800)
        for name in ("memory-direct.fst", "memory-direct.vcd"):
            stray = Path(temp) / name
            if stray.exists():
                stray.unlink()

    # The Picker-generated top contains an unconditional default dumpfile.
    # Verify that normal runs kept it out of the project/evidence tree.
    stray_project = [str(p) for p in (ROOT / "memory-direct.fst", ROOT / "memory-direct.vcd") if p.exists()]
    stray_run = [str(p) for p in output.rglob("*.fst") if p.is_file()]
    per_cycle = [str(p) for p in output.rglob("*.jsonl")]
    per_cycle += [str(p) for p in output.rglob("*trace*.json")]
    policy = {
        "schema_version": 1,
        "format": "mmu-trace-policy-v1",
        "dut": "TLBFA",
        "picker_trace_compiled": True,
        "picker_coverage_compiled": True,
        "runtime_set_waveform": False,
        "per_cycle_signal_dump": False,
        "per_cycle_transaction_dump": False,
        "toffee_keep_coverage_inputs": False,
        "runtime_default_dumpfile_cwd": "temporary directory outside the project",
        "kept_waveforms_in_run": False,
        "stray_waveforms_in_project": stray_project,
        "removed_stale_project_waveforms": removed_stale,
        "stray_waveforms_in_run": stray_run,
        "per_cycle_files": per_cycle,
        "status": "PASS" if not stray_project and not stray_run and not per_cycle else "FAIL",
    }
    output.mkdir(parents=True, exist_ok=True)
    sources = verification_sources()
    (output / "verification-sources.json").write_text(json.dumps({
        "seed": int(os.environ.get("MMU_VERILATOR_SEED", "1")),
        "sources": sources, "command": command,
        "sources_before": before_sources,
        "stable_during_run": before_sources == sources,
        "note": "Both source snapshots must match; build identity is separately in manifest.json."
    }, indent=2) + chr(10))
    (output / "trace-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    print(f"trace policy: {policy['status']}; evidence: {output}")
    raise SystemExit(proc.returncode if policy["status"] == "PASS" and before_sources == sources else 2)


if __name__ == "__main__":
    main()
