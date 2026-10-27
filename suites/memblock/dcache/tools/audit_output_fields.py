#!/usr/bin/env python3
"""P10 audit: which DUT outputs does the bench actually observe?

Grepping `env.py` for pin names is wrong — envs build names like
`f"io_read_resp_{port}_{j}_raw_data"`.  So the authoritative source is the runtime
pin trace produced by `dcacheverify/common/pin_trace.py`:

    DCACHE_PIN_TRACE=/tmp/pins.json pytest tests

That writes `/tmp/pins.json.<pid>` per process; this script merges them and
intersects with each DUT's RTL `output` ports.

Output: manifest/output-field-audit.json with, per DUT, `never_fetched` outputs
plus a coarse bucket (perf / forwarding / spec / sideband).  A port that is never
fetched cannot be compared, so it must not be claimed as checked.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "dcacheverify" / "common"))
from duts import DUTS  # noqa: E402
from pin_trace import merge  # noqa: E402

PORT_RE = re.compile(r"^\s*(input|output)\s+(?:\[[^\]]+\]\s*)?(\w+)")

BUCKETS = [
    (r"^io_perf_", "perf_counter"),
    (r"^io_misstrack_", "misstrack_sideband"),
    (r"^io_mtrack_|^io_spec_query|^io_specmiss", "loadpipe_misstrack_link"),
    (r"forward|stLdFwd", "store_load_forwarding"),
    (r"bits_user_|_bits_echo|bits_corrupt$", "tl_sideband"),
    (r"^io_prefetch_stat|_pf_|prefetch_flag", "prefetch_stat"),
    (r"^io_data_(write|read)|^io_data_readline", "data_array_bundling"),
    (r"^io_tag_|^io_meta_|extra_meta", "tag_meta_bundling"),
    (r"^io_wbq_|^io_block_|conflict", "writeback_conflict"),
    (r"^auto_cacheCtrlOpt|^auto_uncache", "cache_ctrl_slave"),
    (r"spec_fabric", "speculative_fabric"),
    (r"^auto_client_nodes_out_1_", "l2_channel_1"),
    (r"^io_status_dup_", "status_mirror"),
    (r"^io_lsu_release", "ld_ld_violation_hint"),
    (r"boreChildrenBd", "debug_bore"),
    (r"^io_(replace|evict)_|^io_sms_agt_evict", "replacement_hint"),
    (r"^io_(access|latency)_flag_write", "child_block_write_req"),
    (r"^io_banked_data_read|^io_miss_req_bits_(id|isBtoT|occupy_way|cancel)", "child_block_write_req"),
]


def bucket(name: str) -> str:
    for pattern, label in BUCKETS:
        if re.search(pattern, name):
            return label
    return "needs_decision"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin-trace", required=True,
                        help="base path given to DCACHE_PIN_TRACE")
    parser.add_argument("--json", default="manifest/output-field-audit.json")
    args = parser.parse_args()

    fetched = merge(args.pin_trace)
    if not fetched:
        raise SystemExit(f"no pin traces found for {args.pin_trace}.*")

    duts = {}
    for key in DUTS:
        top = ROOT / "rtl" / key / f"{DUTS[key][0]}.sv"
        outs = [m.group(2) for line in top.read_text().splitlines()
                if (m := PORT_RE.match(line)) and m.group(1) == "output"]
        got = fetched.get(key, set())
        never = [p for p in outs if p not in got]
        buckets: dict[str, list[str]] = defaultdict(list)
        for pin in never:
            buckets[bucket(pin)].append(pin)
        duts[key] = {
            "rtl_top": str(top.relative_to(ROOT)),
            "output_count": len(outs),
            "fetched_output_count": len(outs) - len(never),
            "never_fetched_count": len(never),
            "never_fetched_by_bucket": {k: len(v) for k, v in buckets.items()},
            "needs_decision": buckets.pop("needs_decision", []),
        }

    payload = {
        "method": "runtime pin fetch trace (dcacheverify/common/pin_trace.py) vs RTL output ports",
        "note": "a never-fetched output cannot be compared; it must be listed as "
                "unchecked with a reason, not counted as verified",
        "duts": duts,
    }
    out = ROOT / args.json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    for key, info in duts.items():
        print(f"{key:22s} outputs={info['output_count']:4d} "
              f"fetched={info['fetched_output_count']:4d} "
              f"never={info['never_fetched_count']:4d} "
              f"buckets={info['never_fetched_by_bucket']}")
        if info["needs_decision"]:
            print("   needs_decision: " + ", ".join(info["needs_decision"][:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
