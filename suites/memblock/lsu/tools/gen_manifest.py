#!/usr/bin/env python3
"""Generate the pinned LSU RTL closure and SHA-256 manifest.

The source of truth is ``soc-split/rtl`` at the baseline commit. This script is
run once when the baseline is established (or when a baseline upgrade is
explicitly reviewed). ``prepare_rtl.py`` re-verifies every copied byte against
``manifest/lsu-rtl.sha256``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dep_closure import load_index  # noqa: E402
from duts import DUTS, SOC_RTL  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    defined_by, used_by = load_index(SOC_RTL)
    closures: dict[str, dict] = {}
    union: set[str] = set()
    for key, (top, family, layer, role) in DUTS.items():
        if len(defined_by.get(top, [])) != 1:
            raise SystemExit(f"{key}: expected exactly one provider for {top}, "
                             f"got {defined_by.get(top)}")
        needed: set[str] = set()
        queue = [top]
        while queue:
            module = queue.pop()
            for name in defined_by.get(module, []):
                if name in needed:
                    continue
                needed.add(name)
                queue.extend(child for child in used_by[name] if child not in needed)
        missing_modules = sorted({m for m in queue if m not in defined_by})
        if missing_modules:
            raise SystemExit(f"{key}: unresolved modules {missing_modules}")
        files = sorted(needed)
        closures[key] = {
            "top": top,
            "family": family,
            "layer": layer,
            "role": role,
            "files": files,
        }
        union.update(files)

    manifest_lines = []
    for name in sorted(union):
        path = SOC_RTL / name
        if not path.is_file():
            raise SystemExit(f"missing RTL file: {path}")
        manifest_lines.append(f"{sha256(path)}  {name}\n")
    manifest = "".join(manifest_lines)
    (ROOT / "manifest").mkdir(parents=True, exist_ok=True)
    (ROOT / "manifest/lsu-rtl.sha256").write_text(manifest)
    (ROOT / "manifest/closure.json").write_text(
        json.dumps({"schema_version": 1, "source_rtl": str(SOC_RTL),
                    "duts": closures}, indent=2, sort_keys=True) + "\n")
    inventory = {key: {k: v for k, v in closure.items() if k != "role"}
                 for key, closure in closures.items()}
    (ROOT / "manifest/duts.json").write_text(
        json.dumps({"schema_version": 1, "top": "LSU independent UT",
                    "duts": inventory}, indent=2, sort_keys=True) + "\n")

    manifest_hash = hashlib.sha256(manifest.encode()).hexdigest()
    print(f"files={len(union)}")
    print(f"duts={len(closures)}")
    print(f"lsu-rtl.sha256={manifest_hash}")
    for key in DUTS:
        print(f"{key}: {len(closures[key]['files'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
