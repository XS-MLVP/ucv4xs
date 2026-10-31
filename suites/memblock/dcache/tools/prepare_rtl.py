#!/usr/bin/env python3
"""Copy each DUT's minimal RTL closure from soc-split into rtl/<key>/.

Picker builds must not see the whole SoC. This script runs the dependency
closure over the split-verilog tree once per DUT, copies the exact files, writes
`filelist.f`, and records hashes in `manifest/rtl-sha256.json`.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dep_closure import load_index, scan  # noqa: E402
from suites.memblock.dcache.inventory import DUTS, rtl_dir  # noqa: E402
SOC_RTL = ucv_paths.soc_rtl_for(ROOT).resolve()

EXTRA_FILES = ("ClockGate.sv",)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def closure(top: str):
    defined_by, used_by = load_index(SOC_RTL)
    needed: set[str] = set()
    queue = [top]
    while queue:
        module = queue.pop()
        for name in defined_by.get(module, []):
            if name in needed:
                continue
            needed.add(name)
            queue.extend(child for child in used_by[name] if child not in needed)
    for extra in EXTRA_FILES:
        if (SOC_RTL / extra).is_file():
            needed.add(extra)
    return sorted(needed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="*", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    record_path = ROOT / "manifest/rtl-sha256.json"
    record = json.loads(record_path.read_text()) if record_path.is_file() else {}

    for key in args.keys or list(DUTS):
        top, layer, _role = DUTS[key]
        target = rtl_dir(key)
        files = closure(top)
        if target.exists() and not args.force:
            print(f"{key}: exists, skip (use --force)")
            continue
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(SOC_RTL / name, target / name)
        (target / "filelist.f").write_text("".join(f"{name}\n" for name in files))
        hashes = {name: sha256(target / name) for name in files}
        record[key] = {
            "top": top,
            "layer": layer,
            "source_directory": str(SOC_RTL),
            "files": hashes,
        }
        print(f"{key}: {len(files)} files")

    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
