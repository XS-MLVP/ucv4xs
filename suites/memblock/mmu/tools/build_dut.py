#!/usr/bin/env python3
"""Build a minimal Picker DUT for the MMU/TLB verification workspace.

The generated RTL is copied byte-for-byte from soc-split.  Each DUT has a
minimal dependency closure, a recorded SHA-256, and a smoke test that drives
reset and clocks before the build is accepted.
"""
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

ROOT = Path(__file__).resolve().parents[1]
PICKER = str(ucv_paths.project_root() / '.tools/bin/picker')
VERILATOR = Path(str(ucv_paths.project_root() / '.tools/verilator'))

SPECS = {
    "tlbfa": {
        "top": "TLBFA",
        "export_name": "TlbfaDut",
        "rtl_dir": ROOT / "rtl/tlbfa",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/tlbfa-rtl.sha256",
    },
    "wrapper": {
        "top": "TlbStorageWrapper",
        "export_name": "TlbStorageWrapperDut",
        "rtl_dir": ROOT / "rtl/wrapper",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/wrapper-rtl.sha256",
    },
    "tlb": {
        "top": "TLB",
        "export_name": "TlbDut",
        "rtl_dir": ROOT / "rtl/tlb",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/tlb-rtl.sha256",
    },
    "l2mq": {
        "top": "L2TlbMissQueue",
        "export_name": "L2TlbMissQueueDut",
        "rtl_dir": ROOT / "rtl/l2mq",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/l2mq-rtl.sha256",
    },
    "l2pf": {
        "top": "L2TlbPrefetch",
        "export_name": "L2TlbPrefetchDut",
        "rtl_dir": ROOT / "rtl/l2pf",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/l2pf-rtl.sha256",
    },
    "ptwrepeater": {
        "top": "PTWRepeaterNB",
        "export_name": "PtwRepeaterNBDut",
        "rtl_dir": ROOT / "rtl/ptwrepeater",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/ptwrepeater-rtl.sha256",
    },
    "ptwfilter": {
        "top": "PTWFilter",
        "export_name": "PtwFilterDut",
        "rtl_dir": ROOT / "rtl/ptwfilter",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/ptwfilter-rtl.sha256",
    },
    "ptw": {
        "top": "PTW",
        "export_name": "PtwDut",
        "rtl_dir": ROOT / "rtl/ptw",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/ptw-rtl.sha256",
    },
    "pmp": {
        "top": "PMP",
        "export_name": "PmpDut",
        "rtl_dir": ROOT / "rtl/pmp",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/pmp-rtl.sha256",
    },
    "bitmap": {
        "top": "Bitmap",
        "export_name": "BitmapDut",
        "rtl_dir": ROOT / "rtl/bitmap",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/bitmap-rtl.sha256",
    },
    "bitmapcache": {
        "top": "BitmapCache",
        "export_name": "BitmapCacheDut",
        "rtl_dir": ROOT / "rtl/bitmapcache",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/bitmapcache-rtl.sha256",
    },
    "ptwcache": {
        "top": "PtwCache",
        "export_name": "PtwCacheDut",
        "rtl_dir": ROOT / "rtl/ptwcache",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/ptwcache-rtl.sha256",
    },
    "llptw": {
        "top": "LLPTW",
        "export_name": "LlptwDut",
        "rtl_dir": ROOT / "rtl/llptw",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/llptw-rtl.sha256",
    },
    "tlbn": {
        "top": "TLBNonBlock",
        "export_name": "TlbNonBlockDut",
        "rtl_dir": ROOT / "rtl/tlbn",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/tlbn-rtl.sha256",
    },
    "l2tlbwrapper": {
        "top": "L2TLBWrapper",
        "export_name": "L2TlbWrapperDut",
        "rtl_dir": ROOT / "rtl/l2tlbwrapper",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/l2tlbwrapper-rtl.sha256",
    },
    "l2tlb": {
        "top": "L2TLB",
        "export_name": "L2TlbDut",
        "rtl_dir": ROOT / "rtl/l2tlb",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/l2tlb-rtl.sha256",
    },
    "hptw": {
        "top": "HPTW",
        "export_name": "HptwDut",
        "rtl_dir": ROOT / "rtl/hptw",
        "clock": "clock",
        "reset": "reset",
        "hash_manifest": "manifest/hptw-rtl.sha256",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_rtl(spec: dict) -> dict[str, str]:
    expected = {}
    for line in (ROOT / spec["hash_manifest"]).read_text().splitlines():
        digest, name = line.split("  ", 1)
        expected[Path(name).name] = digest
    hashes = {}
    for path in sorted(spec["rtl_dir"].glob("*")):
        if path.suffix not in (".sv", ".v"):
            continue
        digest = sha256(path)
        if expected.get(path.name) != digest:
            raise SystemExit(f"RTL hash mismatch for {path}: {digest}")
        hashes[path.name] = digest
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", choices=sorted(SPECS))
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    spec = SPECS[args.key]
    destination = ROOT / "dut" / args.key
    if destination.exists():
        raise SystemExit(
            f"DUT already exists: {destination}; audit or move it instead of overwriting"
        )
    hashes = verify_rtl(spec)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report_dir = ROOT / "results/builds" / f"{stamp}-{args.key}"
    report_dir.mkdir(parents=True, exist_ok=False)

    command = [
        PICKER,
        "export",
        f"{spec['top']}.sv",
        "--fs",
        "filelist.f",
        "--sname",
        spec["top"],
        "--tname",
        spec["export_name"],
        "--tdir",
        str(destination),
        "--rw",
        "mem_direct",
        "-w",
        "memory-direct.fst",
        "-c",
        "--vflag=--no-coverage-expr --no-coverage-fsm",
        "--lang",
        "python",
        "--cp_lib",
        "1",
        "--autobuild",
        "true",
        "-j",
        str(args.jobs),
    ]
    env = dict(os.environ)
    env["VERILATOR_ROOT"] = str(VERILATOR / "share/verilator")
    env["PATH"] = str(VERILATOR / "bin") + os.pathsep + env.get("PATH", "")
    with (report_dir / "build.log").open("w") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        proc = subprocess.run(
            command,
            cwd=spec["rtl_dir"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    expected_files = [
        "__init__.py",
        "signals.json",
        f"{spec['export_name']}_offset.yaml",
        f"_UT_{spec['export_name']}.so",
        f"libUT{spec['export_name']}.so",
    ]
    missing = [
        name
        for name in expected_files
        if not (destination / name).is_file() or not (destination / name).stat().st_size
    ]
    record = {
        "schema_version": 1,
        "dut": args.key,
        "top": spec["top"],
        "export_name": spec["export_name"],
        "picker": PICKER,
        "picker_version": subprocess.run(
            [PICKER, "--version"], capture_output=True, text=True, check=True
        ).stdout.strip().splitlines()[-1],
        "verilator": str(VERILATOR),
        "command": command,
        "returncode": proc.returncode,
        "missing": missing,
        "rtl_sha256": hashes,
        "trace_compiled": "-w memory-direct.fst",
        "coverage_compiled": "-c",
        "vpi": False,
        "internal_signal_config": False,
        "runtime_policy": "no SetWaveform; temporary cwd; no per-cycle trace",
    }
    record["ok"] = proc.returncode == 0 and not missing
    if record["ok"]:
        smoke = f'''
import importlib.util, sys
from pathlib import Path
p = Path(sys.argv[1]).resolve()
spec = importlib.util.spec_from_file_location("mmu_smoke", p / "__init__.py",
                                              submodule_search_locations=[str(p)])
m = importlib.util.module_from_spec(spec); sys.modules["mmu_smoke"] = m
spec.loader.exec_module(m)
d = m.DUT{spec["export_name"]}()
d.InitClock("{spec["clock"]}")
for s in vars(d).values():
    if callable(getattr(s, "IsInIO", None)) and s.IsInIO() and not s.IsOutIO():
        s.AsImmWrite(); s.Set(0)
d.{spec["reset"]}.Set(1); d.Step(3)
d.{spec["reset"]}.Set(0); d.Step(3)
d.Finish()
print("NATIVE_SMOKE_PASS")
'''
        with tempfile.TemporaryDirectory(prefix="mmu-smoke-", dir=None) as tmp:
            smoke_env = dict(env)
            smoke_env["PYTHONPATH"] = (
                str(ucv_paths.project_root() / '.tools/share/picker/python')
                + os.pathsep
                + smoke_env.get("PYTHONPATH", "")
            )
            smoke_proc = subprocess.run(
                [sys.executable, "-c", smoke, str(destination)],
                cwd=tmp,
                env=smoke_env,
                capture_output=True,
                text=True,
            )
        (report_dir / "smoke.log").write_text(smoke_proc.stdout + smoke_proc.stderr)
        record["ok"] = (
            smoke_proc.returncode == 0 and "NATIVE_SMOKE_PASS" in smoke_proc.stdout
        )
    (report_dir / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{args.key}: {'PASS' if record['ok'] else 'FAILED'}; {report_dir}")
    raise SystemExit(0 if record["ok"] else 1)


if __name__ == "__main__":
    main()
