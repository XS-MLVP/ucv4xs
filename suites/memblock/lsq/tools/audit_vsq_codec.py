#!/usr/bin/env python3
"""Static port/width roundtrip checks; not claimed as DUT functionality."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import re

from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import Redirect, RobPtr
from suites.memblock.lsq.vsq.types import Dispatch, Inputs, encode

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / "rtl/virtual_store_queue/VirtualStoreQueue.sv"
    header = source.read_text().split(");", 1)[0]
    port = re.compile(r"^\s*(input|output)\s+(?:\[(\d+):0\]\s*)?(\w+)\s*[,)]?", re.M)
    ports = {name: (direction, int(high) + 1 if high else 1) for direction, high, name in port.findall(header)}
    inputs = {name: width for name, (direction, width) in ports.items() if direction == "input" and name != "clock"}
    outputs = {name: width for name, (direction, width) in ports.items() if direction == "output"}
    assert len(inputs) == 85 and len(outputs) == 19 and set(inputs) == set(encode(Inputs()))
    rng = random.Random(20261018)
    samples = 0
    for position in range(256):
        requests = tuple(Dispatch(bool(rng.getrandbits(1)), bool(rng.getrandbits(1)), RobPtr.encode(rng.randrange(320), former=bool(rng.getrandbits(1))),
                                  position % 17, SqPtr.encode(position + lane)) for lane in range(8))
        inp = Inputs(requests, RobPtr.encode(position), SqPtr.encode(position), bool(position % 2), Redirect(bool(position % 3), RobPtr.encode(position), bool(position % 2)))
        values = encode(inp)
        assert all(0 <= value < 1 << inputs[name] for name, value in values.items())
        for lane, req in enumerate(requests):
            prefix = f"io_enq_req_{lane}_bits_"
            assert values[prefix + "uop_numLsElem"] == req.flows
            assert (values[prefix + "reqEndPtr_sqIdx_first_flag"], values[prefix + "reqEndPtr_sqIdx_second_flag"], values[prefix + "reqEndPtr_sqIdx_value"]) == (int(req.end.first), int(req.end.second), req.end.value)
        samples += 1
    illegal = (replace(Inputs(), dispatch=(Dispatch(),)), replace(Inputs(), rob_head=RobPtr(value=160)),
               replace(Inputs(), physical_deq=SqPtr(value=64)), replace(Inputs(), dispatch=(Dispatch(flows=17),) + (Dispatch(),) * 7))
    for inp in illegal:
        try:
            encode(inp)
        except ValueError:
            pass
        else:
            raise AssertionError("illegal producer input was silently truncated")
    record = {"status": "static_port_width_and_codec_checked_not_functional_signoff", "inputs_excluding_clock": len(inputs), "outputs": len(outputs),
              "samples": samples, "illegal_rejected": len(illegal), "seed": 20261018,
              "rtl_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "missing_public_fields": ["enq.canAccept", "enq.resp", "reqStartPtr", "deqCount.bits", "uopIdx", "isVec"],
              "ports": {"inputs": inputs, "outputs": outputs}}
    output = ROOT / "results/vsq-codec-static-01"
    output.mkdir(exist_ok=False)
    (output / "report.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in record.items() if key != "ports"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
