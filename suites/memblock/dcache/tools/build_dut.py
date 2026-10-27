#!/usr/bin/env python3
"""Export one DCache DUT with Picker: memory-direct, trace compiled, coverage on.

Mirrors the working flow of the Sbuffer/ICache projects on this machine:
``--rw mem_direct -w memory-direct.fst -c`` with expr/fsm coverage disabled so
only line/toggle/branch are measured. No VPI and no internal-signal
configuration: tests drive and sample public ports only.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from duts import DUTS, dut_dir, export_name, rtl_dir  # noqa: E402

PICKER = str(ucv_paths.project_root() / '.tools/bin/picker')
VERILATOR = Path(str(ucv_paths.project_root() / '.tools/verilator'))

SMOKE = '''
import importlib.util, sys
from pathlib import Path
p = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("dut_smoke", p / "__init__.py",
                                              submodule_search_locations=[str(p)])
m = importlib.util.module_from_spec(spec); sys.modules["dut_smoke"] = m
spec.loader.exec_module(m)
d = getattr(m, "DUT" + sys.argv[2])()
pins = set(d.xport.GetKeys())
for s in list(vars(d).values()):
    if callable(getattr(s, "IsInIO", None)) and s.IsInIO() and not s.IsOutIO():
        s.AsImmWrite(); s.Set(0)
if "clock" in pins:
    d.InitClock("clock")
    if "reset" in pins:
        d.reset.Set(1); d.Step(4); d.reset.Set(0); d.Step(4)
    else:
        d.Step(4)
else:
    # Pure combinational DUT: one evaluation is enough.
    d.Step(1)
d.Finish()
print("NATIVE_SMOKE_PASS")
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", choices=list(DUTS))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    top, layer, role = DUTS[args.key]
    name = export_name(args.key)
    source = rtl_dir(args.key)
    if not (source / "filelist.f").is_file():
        raise SystemExit(f"missing RTL closure: {source}; run tools/prepare_rtl.py first")
    destination = dut_dir(args.key)
    if destination.exists():
        raise SystemExit(f"DUT already exists: {destination}; audit it instead of overwriting")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = ROOT / "results/builds" / f"{stamp}-{args.key}"
    report_dir.mkdir(parents=True, exist_ok=False)
    command = [
        PICKER, "export", f"{top}.sv", "--fs", "filelist.f",
        "--sname", top, "--tname", name,
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
        proc = subprocess.run(command, cwd=source, env=env,
                              stdout=log, stderr=subprocess.STDOUT)
    expected = ["__init__.py", "signals.json", f"{name}_offset.yaml",
                f"_UT_{name}.so", f"libUT{name}.so"]
    missing = [n for n in expected
               if not (destination / n).is_file() or not (destination / n).stat().st_size]
    record = {
        "schema_version": 1,
        "key": args.key,
        "top": top,
        "layer": layer,
        "role": role,
        "export_name": name,
        "picker": PICKER,
        "picker_version": subprocess.run([PICKER, "--version"], capture_output=True,
                                         text=True, check=True).stdout.strip().splitlines()[-1],
        "verilator": str(VERILATOR),
        "command": command,
        "returncode": proc.returncode,
        "missing": missing,
        "trace_compiled": "-w memory-direct.fst",
        "coverage_compiled": "-c",
        "coverage_metrics": ["line", "toggle", "branch"],
        "vpi": False,
        "internal_signal_config": False,
        "run_policy": "no SetWaveform; the Picker default dumpfile is left in a temp cwd",
    }
    record["ok"] = proc.returncode == 0 and not missing
    if record["ok"]:
        with tempfile.TemporaryDirectory(prefix=f"dcache-{args.key}-smoke-",
                                         dir=None) as tmp:
            smoke_env = dict(env)
            smoke_env["PYTHONPATH"] = (
                str(ucv_paths.project_root() / '.tools/share/picker/python') + os.pathsep + smoke_env.get("PYTHONPATH", "")
            )
            run = subprocess.run(
                [sys.executable, "-c", SMOKE, str(destination), name],
                cwd=tmp, env=smoke_env, capture_output=True, text=True)
        (report_dir / "smoke.log").write_text(run.stdout + run.stderr)
        record["smoke"] = {
            "returncode": run.returncode,
            "passed": "NATIVE_SMOKE_PASS" in run.stdout,
        }
        record["ok"] = run.returncode == 0 and record["smoke"]["passed"]
    (report_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{args.key}: {'PASS' if record['ok'] else 'FAILED'}; {report_dir}")
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
