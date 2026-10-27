#!/usr/bin/env python3
"""Exact actual public-pin serialization only, explicitly not functional UT."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lsqverify.psq.decode import decode
from lsqverify.psq.types import Address, Attributes, Data, Inputs, SecondPage, encode
from lsqverify.forward.types import Query, Translation
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import RobPtr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / "rtl/physical_store_queue/PhysicalStoreQueue.sv"
    ports = re.findall(r"^\s*(input|output)\s*(?:\[([^]]+)\]\s*)?(\w+)\s*[,\n]", source.read_text().split(");", 1)[0], re.M)
    widths = {name: int(width.split(":")[0]) + 1 if width else 1 for direction, width, name in ports if direction == "input" and name != "clock"}
    assert len(widths) == 119 and sum(direction == "output" for direction, width, name in ports) == 333
    for index in range(256):
        address = Address(True, index % 64, index * 15 % 4096, (1 << 50) - 256 + index, (1 << 48) - 256 + index,
                          index % 8, bool(index & 1), bool(index & 2), bool(index & 4), bool(index & 8), bool(index & 16))
        inp = Inputs((address, replace(address, slot=(index + 1) % 64)), (Attributes(*(bool(index >> bit & 1) for bit in range(5))), Attributes()),
                     (Data(True, index % 64, index, (1 << 128) - 1 - index), Data()),
                     (SecondPage(True, SqPtr.encode(index), (1 << 48) - 1), SecondPage()),
                     (Query(True, address.vaddr, SqPtr.encode(index), index % 8, True, True, SqPtr.encode(index + 1)),) * 3,
                     (Translation(address.paddr, bool(index & 1)),) * 3, SqPtr.encode(index), SqPtr.encode(index + 1), True, SqPtr.encode(index + 2), True,
                     SqPtr.encode(index + 3), RobPtr.encode(index, former=bool(index & 1)), (True, False), False, True, True, True, True, True, True, True, True, True, bool(index & 1))
        values = encode(inp)
        assert set(values) == set(widths) and all(0 <= value < 1 << widths[key] for key, value in values.items())
        assert decode(values) == inp
    invalid = (replace(Inputs(), addresses=(Address(),)), replace(Inputs(), queries=(Query(),)), replace(Inputs(), rob=RobPtr(value=160)),
               replace(Inputs(), addresses=(Address(slot=64), Address())), replace(Inputs(), enqueue=SqPtr(value=64)),
               replace(Inputs(), addresses=(Address(vaddr=1 << 50), Address())), replace(Inputs(), addresses=(Address(paddr=1 << 48), Address())),
               replace(Inputs(), data=(Data(data=1 << 128), Data())), replace(Inputs(), data=(Data(fu_op=1 << 12), Data())))
    for inp in invalid:
        try:
            encode(inp)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid actual pin width/domain accepted")
    out = ROOT / "results/psq-codec-static-01"
    out.mkdir(exist_ok=False)
    hashes = {}
    for path in (Path(__file__), ROOT / "lsqverify/psq/types.py", ROOT / "lsqverify/psq/decode.py", ROOT / "lsqverify/psq/ports.py"):
        dest = out / "source" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[str(path.relative_to(ROOT))] = sha(dest)
    report = {"status": "static_actual_pin_codec_verified_not_native_functional_ut", "inputs_excluding_clock": 119, "outputs": 333, "width_samples": 256,
              "invalid_rejected": len(invalid), "rtl_sha256": sha(source), "source_hashes": hashes,
              "limits": "All memoryType/control bit combinations here are serialization samples only, not a legal producer or semantic coverage claim."}
    (out / "static-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
