#!/usr/bin/env python3
"""Export real Picker DUTs; preserve builds/logs rather than overwriting evidence."""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from prepare_rtl import ROOT, prepare


def build(key: str, jobs: int) -> dict:
    spec = prepare(key)
    dest = ROOT / "dut" / key
    if dest.exists():
        raise RuntimeError(f"DUT destination already exists; audit it rather than overwrite: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = ROOT / "results/builds" / f"{run}-{key}"
    report_dir.mkdir(parents=True, exist_ok=False)
    lock = __import__("ucv.runtime", fromlist=["toolchain"]).toolchain()
    ver = Path(lock["verilator"]["root"])
    env = dict(os.environ, VERILATOR_ROOT=str(ver / "share/verilator"))
    env["PATH"] = str(ver / "bin") + os.pathsep + env.get("PATH", "")
    cmd = [lock["picker"]["executable"], "export", spec["top"] + ".sv",
           "--fs", "filelist.f", "--sname", spec["top"], "--tname", spec["export_name"],
           "--tdir", str(dest), "--rw", "mem_direct", "-w", "memory-direct.fst", "-c",
           "--vflag=--no-coverage-expr --no-coverage-fsm", "--lang", "python", "--cp_lib", "1",
           "--autobuild", "true", "-j", str(jobs)]
    with (report_dir / "build.log").open("w") as log:
        log.write("$ " + " ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, cwd=ROOT / "rtl" / key, env=env, stdout=log, stderr=subprocess.STDOUT)
    expected = ["__init__.py", "signals.json", spec["export_name"] + "_offset.yaml",
                "_UT_" + spec["export_name"] + ".so", "libUT" + spec["export_name"] + ".so"]
    missing = [n for n in expected if not (dest / n).is_file() or not (dest / n).stat().st_size]
    record = {"key": key, "top": spec["top"], "command": cmd, "returncode": proc.returncode,
              "missing": missing, "rtl": spec["files"], "log": str(report_dir.relative_to(ROOT) / "build.log")}
    record["ok"] = proc.returncode == 0 and not missing
    if record["ok"]:
        # Native package must instantiate and clock; no successful build is inferred from exit code alone.
        code = '''import importlib.util,sys
from pathlib import Path
p=Path(sys.argv[1]); spec=importlib.util.spec_from_file_location("smoke_dut",p/"__init__.py",submodule_search_locations=[str(p)])
m=importlib.util.module_from_spec(spec); sys.modules["smoke_dut"]=m; spec.loader.exec_module(m)
c=next(v for k,v in vars(m).items() if k.startswith("DUT"))
d=c(m.xsp.StringVector(["smoke", "+verilator+seed+1"]),coverage_filename="")
try:
 d.InitClock("clock")
 reset=getattr(d,"reset",None)
 for signal in vars(d).values():
  if callable(getattr(signal,"IsInIO",None)) and signal.IsInIO():
   signal.AsImmWrite(); signal.Set(1 if signal is reset else 0)
 d.Step(3)
finally: d.Finish()
print("NATIVE_SMOKE_PASS")
'''
        # Keep any smoke wave output in an exclusively owned temporary directory.
        with tempfile.TemporaryDirectory(prefix="lsq-smoke-", dir=None) as tmp:
            smoke_env = dict(env)
            smoke_env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + os.pathsep + smoke_env.get("PYTHONPATH", "")
            smoke = subprocess.run([sys.executable, "-c", code, str(dest)], cwd=tmp,
                                   env=smoke_env, capture_output=True, text=True)
        (report_dir / "smoke.log").write_text(smoke.stdout + smoke.stderr)
        record["ok"] = smoke.returncode == 0 and "NATIVE_SMOKE_PASS" in smoke.stdout
        record["smoke_returncode"] = smoke.returncode
    if record["ok"]:
        provenance = {"schema_version": 1, "top": spec["top"], "rtl": spec["files"],
                      "coverage_processor": lock["verilator"]["coverage_processor"],
                      "toolchain": lock, "build_report": str(report_dir.relative_to(ROOT) / "report.json")}
        (dest / "build-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
        record["package_sha256"] = {n: hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in expected}
    (report_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{key}: {'PASS' if record['ok'] else 'FAILED'}; {report_dir.relative_to(ROOT)}", flush=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="+")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    results = [build(key, args.jobs) for key in args.keys]
    raise SystemExit(0 if all(r["ok"] for r in results) else 1)
