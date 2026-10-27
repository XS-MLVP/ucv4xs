#!/usr/bin/env python3
"""Compact a results directory: keep the human/JSON audit trail, shrink the bulk.

A full regression run keeps, per run:

* ``manifest.json``, ``trace-policy.json``, ``seed.json``   (small, canonical)
* ``functional-coverage.json``, ``coverage.html``            (small)
* ``coverage-audit.md``                                      (per-file tables)
* ``coverage-audit-summary.json``                            (per-build numbers)
* ``coverage-audit.json.gz``                                 (per-point audit)
* ``native/<build>/coverage.info.gz``                        (LCOV, gzip)

The raw ``native/<build>/coverage.dat`` (Verilator's point database, tens of MB per
build and only needed to *re-derive* the audit) is removed unless ``--keep-native``
is given.  ``coverage_audit.py`` can always regenerate it by re-running the tests.

Usage: tools/compact_results.py [--keep-native] [--keep RUN ...] RUN [RUN ...]
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def gzip_file(src: Path, dst: Path, level: int = 6) -> int:
    with src.open("rb") as fin, gzip.open(dst, "wb", compresslevel=level) as fout:
        shutil.copyfileobj(fin, fout)
    src.unlink()
    return dst.stat().st_size


def summarise(audit: dict) -> dict:
    """Per-build numbers, small enough to keep as plain JSON."""
    return {
        "format": audit.get("format"),
        "run": audit.get("run"),
        "build_count": audit.get("build_count", len(audit.get("builds", []))),
        "functional_coverage": {
            "coverage": audit["functional_coverage"]["coverage"],
            "groups": [
                {"instance": g["instance"], "coverage": g["coverage"],
                 "samples": g.get("samples")}
                for g in audit["functional_coverage"]["groups"]
            ],
        },
        "builds": [
            {
                "coverage_dat_sha256": b.get("coverage_dat_sha256", "")[:16],
                "lcov_lines_dut_only": b["lcov_lines_dut_only"],
                "branches": {"covered": b["branches"]["covered"],
                             "total": b["branches"]["total"]},
                "toggles_dut_only": {k: b["toggles_dut_only"][k]
                                     for k in ("covered", "total",
                                               "coverage_percent")},
                "functional_coverage": b["functional_coverage"]["coverage"],
            }
            for b in audit.get("builds", [])
        ],
    }


def compact(run: Path, keep_native: bool) -> dict:
    stats = {"run": run.name, "removed_bytes": 0, "gz_audit": 0, "gz_info": 0}
    audit = run / "coverage-audit.json"
    if audit.is_file():
        data = json.loads(audit.read_text())
        (run / "coverage-audit-summary.json").write_text(
            json.dumps(summarise(data), indent=2) + "\n")
        stats["gz_audit"] = gzip_file(audit, audit.with_suffix(".json.gz"))
    native = run / "native"
    if native.is_dir():
        for dat in sorted(native.rglob("coverage.dat")):
            stats["removed_bytes"] += dat.stat().st_size
            if keep_native:
                stats["gz_audit"] += gzip_file(dat, dat.with_suffix(".dat.gz"))
            else:
                dat.unlink()
        # Older seeds were compacted by an earlier script that kept a .dat.gz.
        for stale in sorted(native.rglob("coverage.dat.gz")):
            if not keep_native:
                stats["removed_bytes"] += stale.stat().st_size
                stale.unlink()
        for info in sorted(native.rglob("coverage.info")):
            gz = info.with_suffix(".info.gz")
            if gz.exists():
                info.unlink()
            else:
                stats["gz_info"] += gzip_file(info, gz)
    # Picker rebuild artefacts belong to results/builds, not to a run directory.
    for junk in run.rglob("*.fst"):
        stats["removed_bytes"] += junk.stat().st_size
        junk.unlink()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--keep-native", action="store_true",
                        help="gzip coverage.dat instead of deleting it")
    args = parser.parse_args()
    for name in args.runs:
        run = (ROOT / "results" / name).resolve()
        if not run.is_dir():
            print(f"skip (missing): {name}")
            continue
        stats = compact(run, args.keep_native)
        print(f"{name}: removed {stats['removed_bytes'] / 2**20:.1f} MB, "
              f"audit.gz {stats['gz_audit'] / 2**20:.1f} MB, "
              f"info.gz {stats['gz_info'] / 2**20:.1f} MB")


if __name__ == "__main__":
    main()
