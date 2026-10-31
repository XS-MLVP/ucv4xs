#!/usr/bin/env python3
"""Copy each LSU DUT's minimal RTL closure from soc-split into rtl/<key>/.

Every source byte is checked against the pinned ``manifest/lsu-rtl.sha256``
before copying. Existing copies are never overwritten with different bytes.
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

from dep_closure import load_index  # noqa: E402
from suites.memblock.lsu.inventory import DUTS, rtl_dir  # noqa: E402
SOC_RTL = ucv_paths.soc_rtl_for(ROOT).resolve()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_hashes() -> dict[str, str]:
    path = ROOT / "manifest/lsu-rtl.sha256"
    if not path.is_file():
        raise SystemExit("missing manifest/lsu-rtl.sha256; run tools/gen_manifest.py")
    result = {}
    for line in path.read_text().splitlines():
        digest, name = line.split("  ", 1)
        result[name] = digest
    return result


def closure(top: str) -> list[str]:
    defined_by, used_by = load_index(SOC_RTL)
    needed: set[str] = set()
    queue = [top]
    unresolved: set[str] = set()
    while queue:
        module = queue.pop()
        providers = defined_by.get(module)
        if not providers:
            unresolved.add(module)
            continue
        for name in providers:
            if name in needed:
                continue
            needed.add(name)
            queue.extend(child for child in used_by[name] if child not in needed)
    if unresolved:
        raise SystemExit(f"{top}: unresolved modules {sorted(unresolved)}")
    return sorted(needed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("keys", nargs="*", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    hashes = pinned_hashes()

    for key in args.keys or list(DUTS):
        if key not in DUTS:
            raise SystemExit(f"unknown DUT key: {key}")
        top = DUTS[key][0]
        files = closure(top)
        unknown = [name for name in files if name not in hashes]
        if unknown:
            raise SystemExit(f"{key}: closure files not in pinned manifest: {unknown}")
        for name in files:
            source = SOC_RTL / name
            if sha256(source) != hashes[name]:
                raise SystemExit(f"source RTL differs from pinned baseline: {name}")
        target = rtl_dir(key)
        target.mkdir(parents=True, exist_ok=True)
        for name in files:
            destination = target / name
            digest = hashes[name]
            if destination.exists() and sha256(destination) != digest:
                raise SystemExit(f"{key}: refusing to overwrite differing RTL: {destination}")
            if not destination.exists():
                shutil.copy2(SOC_RTL / name, destination)
            if sha256(destination) != digest:
                raise SystemExit(f"{key}: copy hash mismatch: {destination}")
        filelist = "".join(f"{name}\n" for name in files)
        existing = (target / "filelist.f")
        if existing.exists() and existing.read_text() != filelist and not args.force:
            raise SystemExit(f"{key}: differing filelist.f; use --force only after review")
        existing.write_text(filelist)
        record = {
            "schema_version": 1,
            "key": key,
            "top": top,
            "family": DUTS[key][1],
            "layer": DUTS[key][2],
            "role": DUTS[key][3],
            "source_rtl": str(SOC_RTL),
            "files": {name: hashes[name] for name in files},
        }
        (target / "source.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"{key}: {len(files)} files -> {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
