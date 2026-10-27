#!/usr/bin/env python3
"""Export the single Sbuffer DUT with memory-direct, trace and coverage.

Trace support is compiled in (-w) and coverage is compiled in (-c). Normal runs
never call SetWaveform; Picker's generated top still contains a default
``$dumpfile("memory-direct.fst")``, so the runner executes from a temporary
working directory and drops that file. This mirrors the toffee main-branch
cache/e203 flow (``--rw mem_direct --coverage``): no VPI and no internal-signal
configuration are enabled.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PICKER = str(ucv_paths.project_root() / '.tools/bin/picker')
VERILATOR = Path(str(ucv_paths.project_root() / '.tools/verilator'))
SPEC = {
    "key": "sbuffer",
    "top": "Sbuffer",
    "export_name": "SbufferDut",
    "rtl_dir": ROOT / "rtl/sbuffer",
    "dlc": ["Sbuffer.sv", "SbufferData.sv"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_rtl() -> dict[str, str]:
    expected = {}
    for line in (ROOT / "manifest/sbuffer-rtl.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    for name in SPEC["dlc"]:
        path = SPEC["rtl_dir"] / name
        digest = sha256(path)
        recorded = (expected.get(name)
                    or expected.get(f"rtl/sbuffer/{name}")
                    or expected.get(f"rtl/sbuffer_data/{name}"))
        if recorded != digest:
            raise SystemExit(f"RTL hash mismatch for {path}: {digest} != {recorded}")
    return {name: sha256(SPEC["rtl_dir"] / name) for name in SPEC["dlc"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()

    destination = ROOT / "dut" / SPEC["key"]
    if destination.exists():
        raise SystemExit(
            f"DUT already exists: {destination}; audit or move it instead of overwriting"
        )
    hashes = verify_rtl()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = ROOT / "results/builds" / f"{stamp}-{SPEC['key']}"
    report_dir.mkdir(parents=True, exist_ok=False)
    command = [
        PICKER, "export", f"{SPEC['top']}.sv", "--fs", "filelist.f",
        "--sname", SPEC["top"], "--tname", SPEC["export_name"],
        "--tdir", str(destination), "--rw", "mem_direct",
        "-w", "memory-direct.fst", "-c",
        "--vflag=--no-coverage-expr --no-coverage-fsm",
        "--lang", "python", "--cp_lib", "1", "--autobuild", "true",
        "-j", str(args.jobs),
    ]
    env = dict(os.environ)
    env["VERILATOR_ROOT"] = str(VERILATOR / "share/verilator")
    env["PATH"] = str(VERILATOR / "bin") + os.pathsep + env.get("PATH", "")
    with (report_dir / "build.log").open("w") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        proc = subprocess.run(command, cwd=SPEC["rtl_dir"], env=env,
                              stdout=log, stderr=subprocess.STDOUT)
    expected = ["__init__.py", "signals.json", f"{SPEC['export_name']}_offset.yaml",
                f"_UT_{SPEC['export_name']}.so", f"libUT{SPEC['export_name']}.so"]
    missing = [name for name in expected
               if not (destination / name).is_file() or not (destination / name).stat().st_size]
    record = {
        "schema_version": 1,
        "top": SPEC["top"],
        "export_name": SPEC["export_name"],
        "picker": PICKER,
        "picker_version": subprocess.run([PICKER, "--version"], capture_output=True,
                                          text=True, check=True).stdout.strip().splitlines()[-1],
        "verilator": str(VERILATOR),
        "command": command,
        "returncode": proc.returncode,
        "missing": missing,
        "rtl_sha256": hashes,
        "trace_compiled": "-w memory-direct.fst",
        "coverage_compiled": "-c",
        "vpi": False,
        "internal_signal_config": False,
        "runtime_policy": "no SetWaveform; Picker default dumpfile goes to the run temp cwd",
    }
    record["ok"] = proc.returncode == 0 and not missing
    if record["ok"]:
        smoke = '''
import importlib.util, os, sys
from pathlib import Path
p = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("sbuffer_smoke", p / "__init__.py",
                                              submodule_search_locations=[str(p)])
m = importlib.util.module_from_spec(spec); sys.modules["sbuffer_smoke"] = m
spec.loader.exec_module(m)
d = m.DUTSbufferDut()
d.InitClock("clock")
for s in vars(d).values():
    if callable(getattr(s, "IsInIO", None)) and s.IsInIO() and not s.IsOutIO():
        s.AsImmWrite(); s.Set(0)
d.io_sqempty.Set(1); d.io_mshr_store_empty.Set(1)
d.reset.Set(1); d.Step(3); d.reset.Set(0); d.Step(3)
d.Finish()
print("NATIVE_SMOKE_PASS")
'''
        with tempfile.TemporaryDirectory(prefix="sbuffer-smoke-", dir=None) as tmp:
            smoke_env = dict(env)
            smoke_env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + os.pathsep + smoke_env.get("PYTHONPATH", "")
            run = subprocess.run([sys.executable, "-c", smoke, str(destination)],
                                 cwd=tmp, env=smoke_env, capture_output=True, text=True)
        (report_dir / "smoke.log").write_text(run.stdout + run.stderr)
        record["ok"] = run.returncode == 0 and "NATIVE_SMOKE_PASS" in run.stdout
    (report_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{SPEC['key']}: {'PASS' if record['ok'] else 'FAILED'}; {report_dir}")
    raise SystemExit(0 if record["ok"] else 1)


if __name__ == "__main__":
    main()
