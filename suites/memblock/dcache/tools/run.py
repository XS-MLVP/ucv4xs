#!/usr/bin/env python3
"""Run DCache UT through the toffee main-branch runner.

Normal runs never call SetWaveform; Picker's generated top still has a default
``$dumpfile``, so pytest runs from a temporary cwd. No per-cycle signal or
transaction dumps are produced, and a fresh output directory is mandatory.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = __import__("ucv.runtime", fromlist=["toolchain"]).toolchain()
TOFFEE = shlex.split(LOCK["toffee"]["runner_command"])
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
    with tempfile.TemporaryDirectory(prefix="dcache-run-", dir=None) as temp:
        proc = subprocess.run(command, cwd=temp, env=dict(os.environ))
        for name in ("memory-direct.fst", "memory-direct.vcd"):
            stray = Path(temp) / name
            if stray.exists():
                stray.unlink()
    stray_project = [str(p) for p in (ROOT / "memory-direct.fst", ROOT / "memory-direct.vcd") if p.exists()]
    stray_run = [str(p) for p in output.rglob("*.fst") if p.is_file()]
    per_cycle = [str(p) for p in output.rglob("*.jsonl")]
    per_cycle += [str(p) for p in output.rglob("*trace*.json")]
    policy = {
        "schema_version": 1,
        "format": "dcache-trace-policy-v1",
        "picker_trace_compiled": True,
        "picker_coverage_compiled": True,
        "runtime_set_waveform": False,
        "per_cycle_signal_dump": False,
        "per_cycle_transaction_dump": False,
        "toffee_keep_coverage_inputs": False,
        "runtime_default_dumpfile_cwd": "temporary directory outside the project",
        "kept_waveforms_in_run": False,
        "stray_waveforms_in_project": stray_project,
        "removed_stale_project_waveforms": removed,
        "stray_waveforms_in_run": stray_run,
        "per_cycle_files": per_cycle,
        "status": "PASS" if not stray_project and not stray_run and not per_cycle else "FAIL",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "trace-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    seeds = {
        "verilator_seed": os.environ.get("DCACHE_VERILATOR_SEED", "1"),
        "python_seed": os.environ.get("DCACHE_TEST_RANDOM_SEED", "1"),
    }
    (output / "seed.json").write_text(json.dumps(seeds, indent=2) + "\n")
    print(f"trace policy: {policy['status']}; evidence: {output}")
    raise SystemExit(proc.returncode if policy["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
