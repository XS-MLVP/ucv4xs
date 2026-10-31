#!/usr/bin/env python3
"""Static exact-pin encode/decode audit, explicitly not native functional UT."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from suites.memblock.lsq.deq.ports import Ports
from suites.memblock.lsq.deq.types import DeqControl, Inputs, SecondPage, Store, encode
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Pin:
    def __init__(self):
        self.value = 0

    def U(self):
        return self.value


def main():
    source = ROOT / "rtl/deq_module/DeqModule.sv"
    declarations = re.findall(r"^\s*(input|output)\s*(?:\[([^]]+)\]\s*)?(\w+)\s*[,\n]", source.read_text().split(");", 1)[0], re.M)
    inputs = {name: int(width.split(":")[0]) + 1 if width else 1 for direction, width, name in declarations if direction == "input" and name != "clock"}
    outputs = {name: int(width.split(":")[0]) + 1 if width else 1 for direction, width, name in declarations if direction == "output"}
    fake = type("StaticPinBinding", (), {name: Pin() for name in (*inputs, *outputs)})()
    ports = Ports(fake)
    assert len(inputs) == 61 and len(outputs) == 55 and set(ports.outputs) == set(outputs)
    for index in range(256):
        store = Store((1 << 50) - 16 + index % 16, (1 << 36) - 1, (1 << 16) - 1, (1 << 128) - 1, index % 8, index % 4,
                      bool(index & 1), bool(index & 2), bool(index & 4), bool(index & 8), bool(index & 16), bool(index & 32), bool(index & 64), bool(index & 128))
        inp = Inputs((store, store), (DeqControl(True, True, False), DeqControl(False, False, True)), (bool(index & 1), bool(index & 2)),
                     SqPtr.encode(index), (SqPtr.encode(index + 1), SqPtr.encode(index + 2)), RobPtr.encode(index, former=bool(index & 1)), index % 65,
                     uncache_ready=True, uncache_ack_valid=True, uncache_ack_to_load=True, uncache_response=True,
                     cache_ready=True, cache_response=True, cache_denied=True, cache_corrupt=True, writeback_ready=True,
                     second_page=SecondPage(True, (1 << 48) - 1, SqPtr.encode(index + 3)))
        pins = encode(inp)
        assert set(pins) == set(inputs) and all(0 <= value < 1 << inputs[name] for name, value in pins.items())
        for name, value in pins.items():
            getattr(fake, name).value = value
        decoded, observed = ports.sample(None)
        assert encode(decoded) == pins and observed == {name: 0 for name in outputs}
    invalid = (replace(Inputs(), stores=(Store(),)), replace(Inputs(), dequeue_controls=(DeqControl(),)),
               replace(Inputs(), stores=(Store(vaddr=1 << 50), Store())), replace(Inputs(), stores=(Store(data=1 << 128), Store())),
               replace(Inputs(), valid_count=65), replace(Inputs(), rob=RobPtr(value=160)),
               replace(Inputs(), read_ptr=SqPtr(value=64)), replace(Inputs(), second_page=SecondPage(paddr=1 << 48)))
    for inp in invalid:
        try:
            encode(inp)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid public width was silently truncated")
    out = ROOT / "results/deq-codec-static-01"
    out.mkdir(exist_ok=False)
    hashes = {}
    for path in (Path(__file__), *(ROOT / "deq").glob("*.py")):
        dest = out / "source" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[str(path.relative_to(ROOT))] = sha(dest)
    report = {"status": "static_public_codec_and_decode_verified_not_native_ut", "inputs_excluding_clock": 61, "outputs": 55, "valid_width_samples": 256,
              "invalid_rejected": len(invalid), "rtl_sha256": sha(source), "frozen_sources": hashes,
              "limits": "All eight memoryType bit encodings tested only for serialization; not a legal-traffic or functional claim. Deleted lane1 fields are projected out, not fabricated. No functional checked bins, clocked response checker or coverage is established here."}
    (out / "static-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
