#!/usr/bin/env python3
"""Build ICache DUTs with picker using the pinned memory-direct flow.

Each DUT gets a minimal RTL closure under ``rtl/<dut>/`` and is exported to
``dut/<dut>/``. The options mirror the BPU verification project so that both
share the same xcomm ABI (3) and coverage descriptor protocol (5).
"""

from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERILATOR_ROOT = Path(str(ucv_paths.project_root() / '.tools/verilator'))
PICKER = Path(str(ucv_paths.project_root() / '.tools/bin/picker'))

# dut key -> (RTL top module, generated DUT class name)
DUTS: dict[str, tuple[str, str]] = {
    "waylookup": ("ICacheWayLookup", "WayLookupDut"),
    "replacer": ("ICacheReplacer", "ReplacerDut"),
    "mshr": ("ICacheMshr", "MshrDut"),
    "databank": ("ICacheDataBank", "DataBankDut"),
    "metabank": ("ICacheMetaInterleavedBank", "MetaBankDut"),
    "metaarray": ("ICacheMetaArray", "MetaArrayDut"),
    "dataarray": ("ICacheDataArray", "DataArrayDut"),
    "missunit": ("ICacheMissUnit", "MissUnitDut"),
    "mainpipe": ("ICacheMainPipe", "MainPipeDut"),
    "prefetchpipe": ("ICachePrefetchPipe", "PrefetchPipeDut"),
    "icache": ("ICache", "ICacheDut"),
}

PACKAGE_FILES_UNUSED = (
    "__init__.py",
    "signals.json",
    f"{'{}'}_offset.yaml",
    "_UT_{}.so",
    "libUT{}.so",
)


def check_toolchain() -> None:
    if not PICKER.is_file():
        raise SystemExit(f"picker not found at {PICKER}")
    if not (VERILATOR_ROOT / "bin" / "verilator").is_file():
        raise SystemExit(f"verilator not found under {VERILATOR_ROOT}")
    out = subprocess.run([str(PICKER), "-v"], capture_output=True, text=True)
    print(out.stdout.strip().splitlines()[-1] if out.stdout else out.stderr.strip(), flush=True)


def build(key: str, *, jobs: int, clean: bool) -> dict:
    top, tname = DUTS[key]
    src = ROOT / "rtl" / key
    dest = ROOT / "dut" / key
    if not (src / "filelist.f").is_file():
        raise SystemExit(f"missing filelist for {key}; run tools/dep_closure.py")

    # picker requires --tdir to not exist yet; it creates it itself.
    stage = Path(str(ucv_paths.scratch_root())) / f"icache-dut-{key}"
    if stage.exists():
        shutil.rmtree(stage)

    env = dict(os.environ)
    env["VERILATOR_ROOT"] = str(VERILATOR_ROOT / "share" / "verilator")
    env["PATH"] = f"{VERILATOR_ROOT / 'bin'}:{env.get('PATH', '')}"

    cmd = [
        str(PICKER), "export", f"{top}.sv",
        "--fs", "filelist.f",
        "--sname", top,
        "--tname", tname,
        "--tdir", str(stage),
        "--rw", "mem_direct",
        "-w", "memory-direct.fst",
        "-c",
        "--vflag=--no-coverage-expr --no-coverage-fsm",
        "--lang", "python",
        "--cp_lib", "1",
        "--autobuild", "true",
        "-j", str(jobs),
    ]
    started = time.time()
    log = ROOT / "results" / f"build-{key}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as fh:
        fh.write("$ " + " ".join(cmd) + "\n\n")
        fh.flush()
        result = subprocess.run(cmd, cwd=src, env=env, stdout=fh, stderr=subprocess.STDOUT)
    elapsed = time.time() - started

    text = log.read_text(errors="replace")
    record = {
        "dut": key,
        "top": top,
        "tname": tname,
        "exit_code": result.returncode,
        "seconds": round(elapsed, 1),
        "log": str(log.relative_to(ROOT)),
    }

    # picker's exit code is not a reliable verdict (its own docs warn the
    # opposite direction too). The project accepts a DUT only after the
    # package files exist and the model actually instantiates, so mirror that.
    expected = {
        "__init__.py",
        "signals.json",
        f"{tname}_offset.yaml",
        f"_UT_{tname}.so",
        f"libUT{tname}.so",
    }
    present = {p.name for p in stage.iterdir()} if stage.is_dir() else set()
    missing = expected - present
    empty = sorted(
        p.name for p in stage.iterdir()
        if p.is_file() and p.stat().st_size == 0
    ) if stage.is_dir() else []
    record["missing"] = sorted(missing)
    record["empty"] = empty

    hint = [ln for ln in text.splitlines()
            if any(m in ln for m in ("Error:", "error:", "%Error", "Traceback"))]
    record["error_lines"] = hint[:10]

    if missing or empty:
        record["ok"] = False
        print(f"[{key}] FAILED rc={result.returncode} missing={sorted(missing)} "
              f"empty={empty} ({elapsed:.0f}s)", flush=True)
        return record

    smoke = _smoke_instantiate(stage, tname)
    record["smoke"] = smoke
    if not smoke["ok"]:
        record["ok"] = False
        print(f"[{key}] FAILED smoke: {smoke['error']} ({elapsed:.0f}s)", flush=True)
        return record

    if clean and dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for item in stage.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    record["ok"] = True
    record["package"] = sorted(p.name for p in dest.iterdir())
    print(f"[{key}] OK {elapsed:.0f}s -> dut/{key}", flush=True)
    return record


def _smoke_instantiate(stage: Path, tname: str) -> dict:
    """Import the generated package in a child process and clock it once."""
    code = f'''
import importlib.util, pathlib, sys
d = pathlib.Path({str(stage)!r})
spec = importlib.util.spec_from_file_location("smoke", d / "__init__.py",
                                             submodule_search_locations=[str(d)])
m = importlib.util.module_from_spec(spec)
sys.modules["smoke"] = m
spec.loader.exec_module(m)
cls = next(v for k, v in vars(m).items() if k.startswith("DUT"))
args = m.xsp.StringVector([{tname!r}, "+verilator+seed+1"])
dut = cls(args, coverage_filename="")
dut.InitClock("clock")
dut.Step(2)
dut.Finish()
print("SMOKE_OK")
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + ":" + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    ok = proc.returncode == 0 and "SMOKE_OK" in proc.stdout
    return {
        "ok": ok,
        "error": "" if ok else (proc.stderr.strip().splitlines() or [""])[-1],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("duts", nargs="*", default=[], help=f"subset of {sorted(DUTS)}")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--no-clean", action="store_true")
    ap.add_argument("--report", type=Path, default=ROOT / "results" / "build-report.json")
    args = ap.parse_args()

    keys = args.duts or list(DUTS)
    unknown = [k for k in keys if k not in DUTS]
    if unknown:
        raise SystemExit(f"unknown DUT(s): {unknown}")

    check_toolchain()
    records = []
    for key in keys:
        records.append(build(key, jobs=args.jobs, clean=not args.no_clean))
    args.report.write_text(json.dumps(records, indent=2) + "\n")

    bad = [r["dut"] for r in records if not r["ok"]]
    print(f"\nbuilt {len(records) - len(bad)}/{len(records)}; failed: {bad or 'none'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
