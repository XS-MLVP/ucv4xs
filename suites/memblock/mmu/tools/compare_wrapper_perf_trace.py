#!/usr/bin/env python3
"""Compare L2TLB and L2TLBWrapper cycle traces.

The wrapper is a pure pass-through plus two extra RegNext stages on every
performance-event output.  With identical reset and stimulus, all functional
signals must match cycle-for-cycle and every wrapper perf bit must equal the
L2TLB perf bit two cycles earlier (ignoring the initial random pipeline fill).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FUNCTIONAL = ("resp_valid", "resp_ppn", "resp_level", "resp_v", "req_ready",
              "a_valid", "a_addr", "wfi_safe")
PERF_COUNT = 19
IGNORE_CYCLES = 4


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("l2tlb")
    parser.add_argument("wrapper")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    child = json.loads(Path(args.l2tlb).read_text())
    wrapper = json.loads(Path(args.wrapper).read_text())
    failures: list[str] = []
    if len(child) != len(wrapper):
        failures.append(f"trace length {len(wrapper)} != {len(child)}")
    cycles = min(len(child), len(wrapper))
    for cycle in range(cycles):
        for field in FUNCTIONAL:
            if wrapper[cycle][field] != child[cycle][field]:
                failures.append(
                    f"cycle {cycle} {field}: wrapper={wrapper[cycle][field]} "
                    f"l2tlb={child[cycle][field]}")
        if cycle >= IGNORE_CYCLES:
            for index in range(PERF_COUNT):
                expected = child[cycle - 2]["perf"][index]
                actual = wrapper[cycle]["perf"][index]
                if actual != expected:
                    failures.append(
                        f"cycle {cycle} perf[{index}]: wrapper={actual} "
                        f"l2tlb[t-2]={expected}")
    pulses = {
        "l2tlb": {str(i): [r["cycle"] for r in child if r["perf"][i]]
                  for i in range(PERF_COUNT)},
        "wrapper": {str(i): [r["cycle"] for r in wrapper if r["perf"][i]]
                    for i in range(PERF_COUNT)},
    }
    result = {
        "format": "mmu-wrapper-perf-trace-comparison-v1",
        "l2tlb_trace": str(Path(args.l2tlb).resolve()),
        "wrapper_trace": str(Path(args.wrapper).resolve()),
        "cycles": cycles,
        "functional_fields": list(FUNCTIONAL),
        "perf_shift_cycles": 2,
        "initial_cycles_ignored": IGNORE_CYCLES,
        "pulses": pulses,
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"], f"{len(failures)} failures", f"cycles={cycles}")
    for failure in failures[:20]:
        print(" -", failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
