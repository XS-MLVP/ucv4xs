#!/usr/bin/env python3
"""Paired checker-sensitivity controls (P03/P04/P06/P12).

For each (mutation, test) pair:

1. run the test unmutated  -> must PASS
2. run it with the oracle deliberately corrupted -> must FAIL

A pair where (2) still passes means the assertion does not depend on the value it
claims to check.  That is a checker finding, not an RTL finding.

Writes ``manifest/checker-selfcheck.json`` and prints a table.
"""
from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = Path(str(ucv_paths.project_root() / '.venv/bin/python'))

PAIRS = [
    ("bda_readback", "tests/banked_data_array/test_banked_data_array.py::test_read_window_all_ports_and_ways"),
    ("cf_expected", "tests/counter_filter/test_counter_filter.py::test_random_legal_traffic"),
    ("dta_readback", "tests/duplicated_tag_array/test_duplicated_tag_array.py::test_set_independence_and_boundaries"),
    ("mq_expected", "tests/miss_queue/test_miss_queue.py::test_two_beat_refill_installs_line"),
    ("lp_expected", "tests/load_pipe/test_load_pipe.py::test_outcome_way_matrix"),
    ("mp_expected", "tests/main_pipe/test_main_pipe.py::test_amo_miss_request_and_replay"),
    ("dcache_readback", "tests/dcache/test_dcache.py::test_cold_miss_refill_then_hit"),
    ("store_hit_readback", "tests/dcache/test_dcache.py::test_store_then_load_observes_data"),
]


def run(nodeid: str, mutation: str | None) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ucv_paths.project_root() / '.tools/share/picker/python') + ":" + str(ROOT)
    if mutation:
        env["DCACHE_MUTATION"] = mutation
    else:
        env.pop("DCACHE_MUTATION", None)
    cmd = [str(VENV) if VENV.is_file() else sys.executable,
           "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
           "-p", "tools._mutation_plugin"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    tail = (proc.stdout + proc.stderr)[-1500:]
    return proc.returncode, tail


def verdict(rc: int) -> str:
    if rc == 0:
        return "PASS"
    if rc == 1:
        return "FAIL"
    return f"ERROR({rc})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="manifest/checker-selfcheck.json")
    parser.add_argument("--only", default=None)
    args = parser.parse_args()

    rows = []
    ok = True
    for mutation, nodeid in PAIRS:
        if args.only and args.only not in mutation:
            continue
        base_rc, base_tail = run(nodeid, None)
        mut_rc, mut_tail = run(nodeid, mutation)
        base, mutated = verdict(base_rc), verdict(mut_rc)
        good = base == "PASS" and mutated == "FAIL"
        ok = ok and good
        rows.append({
            "mutation": mutation,
            "nodeid": nodeid,
            "baseline": base,
            "mutated": mutated,
            "sensitive": good,
            "mutated_tail": mut_tail if not good else "",
        })
        print(f"{mutation:20s} {base:5s} -> {mutated:5s} "
              f"{'OK' if good else 'NOT SENSITIVE'}  {nodeid.split('::')[-1]}")
        if not good:
            print(mut_tail)

    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "method": "unmutated must PASS, corrupted oracle must FAIL",
        "pairs": rows,
        "sensitive_pairs": sum(1 for r in rows if r["sensitive"]),
        "total_pairs": len(rows),
    }, indent=2) + "\n")
    print(f"\nsensitive {sum(1 for r in rows if r['sensitive'])}/{len(rows)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
