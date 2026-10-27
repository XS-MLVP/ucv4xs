#!/usr/bin/env python3
"""Serialize every retained LoadQueue input; this is NOT a functional UT."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lsqverify.load_queue.codec import encode, ports
from lsqverify.load_queue.ports import decode
from lsqverify.load_queue.types import Bus, Bypass, Inputs, Load
from lsqverify.raw.types import SqPtr
from lsqverify.replay.types import Enqueue, Uop
from lsqverify.vlq.types import Dispatch, QueuePtr, RobPtr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    rng = random.Random(20261018)
    spec = ports()
    seen = {name: set() for name in spec["input"]}
    for _ in range(256):
        pins = {name: rng.randrange(1 << width) for name, width in spec["input"].items()}
        for name in pins:
            if name.endswith("robIdx_value") or name in ("io_rob_pendingPtr_value", "io_rob_pendingPtrNext_value"):
                pins[name] %= 160
            elif name.endswith("lqIdx_value"):
                pins[name] %= 120
            elif name.endswith("numLsElem"):
                pins[name] %= 17
        for lane in range(3):
            p = f"io_ldu_ldin_{lane}_"
            if pins[p + "bits_rep_info_need_rep"]:
                cause = rng.randrange(12)
                for bit in range(13):
                    pins[p + f"bits_rep_info_cause_{bit}"] = int(bit == cause)
            if pins[p + "valid"] and pins[p + "bits_isLoadReplay"]:
                pins[p + "bits_schedIndex"] %= 120
        got = encode(decode(pins))
        assert got == pins
        for name, value in pins.items():
            seen[name].add(value)
    assert all(len(values) > 1 for values in seen.values())
    invalid = {
        "lane_shape": Inputs(loads=(Load(),) * 2),
        "dispatch_flows": Inputs(dispatch=(Dispatch(flows=17),) + (Dispatch(),) * 7),
        "rob_slot": Inputs(pending=RobPtr(value=160)),
        "lq_slot": Inputs(bypass=(Bypass(lq=QueuePtr(value=120)),) + (Bypass(),) * 2),
        "sq_slot": Inputs(address_ready=SqPtr(value=64)),
        "wide_vaddr": Inputs(loads=(Load(Enqueue(vaddr=1 << 50)),) + (Load(),) * 2),
        "sid_width": Inputs(bus=Bus(sid=16)),
        "non_one_hot_cause": Inputs(loads=(Load(Enqueue(valid=True, need_replay=True, causes=3)),) + (Load(),) * 2),
        "deleted_exception": Inputs(loads=(Load(exceptions=1 << 1),) + (Load(),) * 2),
    }
    rejected = []
    for label, inp in invalid.items():
        try:
            encode(inp)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError(("illegal packet accepted", label))
    for name in ("rar_full", "raw_full", "writeback", "mmio_wakeup", "nc_wakeup"):
        try:
            Inputs(**{name: True})
        except TypeError:
            rejected.append("no_driveable_internal_" + name)
        else:
            raise AssertionError("internal feedback exposed as a fake external stimulus")
    build = json.loads((ROOT / "dut/load_queue/build-provenance.json").read_text())
    report = dict(status="static_622_input_codec_and_independent_passive_decode_pass", samples=256,
                  inputs=len(spec["input"]), outputs=len(spec["output"]), all_inputs_varied=True, illegal_packets_rejected=rejected,
                  original_top_sha256=build["rtl"]["LoadQueue.sv"], original_closure_files=len(build["rtl"]),
                  checked_files={str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT / "lsqverify/load_queue/types.py", ROOT / "lsqverify/load_queue/codec.py", ROOT / "lsqverify/load_queue/ports.py")},
                  limits="Adapter widths/serialization only. Random raw encodings are not a legal traffic stream and give no DUT, lifecycle or functional coverage credit. All functional UT uses the real native DUT and managed X Reactor runner.")
    out = ROOT / "results/static/load-queue-codec-v1.json"
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    audit()
