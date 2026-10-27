#!/usr/bin/env python3
"""Actual StoreQueue external serialization, not native functional coverage."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lsqverify.forward.types import Query, Translation
from lsqverify.psq.types import Address, Attributes, Data, SecondPage
from lsqverify.raw.types import SqPtr
from lsqverify.store_queue.decode import decode
from lsqverify.store_queue.types import Inputs, encode
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / "rtl/store_queue/StoreQueue.sv"
    ports = re.findall(r"^\s*(input|output)\s*(?:\[([^]]+)\]\s*)?(\w+)\s*[,\n]", source.read_text().split(");", 1)[0], re.M)
    widths = {name: int(width.split(":")[0]) + 1 if width else 1 for direction, width, name in ports if direction == "input" and name != "clock"}
    assert len(widths) == 182 and sum(direction == "output" for direction, width, name in ports) == 338
    assert not any(name.startswith(("io_fromVirtualStoreQueue_", "io_fromPhysicalQueue_")) for name in widths)
    for index in range(256):
        inp = Inputs(dispatch=tuple(Dispatch(bool(index >> lane % 8 & 1), bool(index >> (lane + 1) % 8 & 1), RobPtr.encode(index + lane, former=bool(lane % 2)),
                                             (index + lane) % 17, SqPtr.encode(index + lane)) for lane in range(8)),
                     rob_head=RobPtr.encode(index), redirect=Redirect(bool(index & 1), RobPtr.encode(index + 2), bool(index & 2)),
                     addresses=tuple(Address(True, (index + lane) % 64, index * 13 % 4096, (1 << 50) - 256 + index, (1 << 48) - 256 + index,
                                             index % 8, bool(index & 1), bool(index & 2), bool(index & 4), bool(index & 8), bool(index & 16)) for lane in range(2)),
                     attributes=(Attributes(*(bool(index >> bit & 1) for bit in range(5))), Attributes()),
                     data=(Data(True, index % 64, index * 9, (1 << 128) - 1 - index), Data()),
                     second_pages=(SecondPage(True, SqPtr.encode(index), (1 << 48) - 1), SecondPage()),
                     queries=(Query(True, index, SqPtr.encode(index), index % 8, True, True, SqPtr.encode(index + 1)),) * 3,
                     translations=(Translation((1 << 48) - 1 - index, bool(index & 1)),) * 3, sbuffer_ready=(True, False), sbuffer_empty=bool(index & 1),
                     cache_ready=True, cache_response=True, cache_denied=True, cache_corrupt=True, uncache_ready=True, uncache_ack_valid=True,
                     uncache_ack_to_load=True, uncache_response=True, writeback_ready=True, reset=bool(index & 1))
        values = encode(inp)
        assert set(values) == set(widths) and all(0 <= value < 1 << widths[key] for key, value in values.items())
        assert decode(values) == inp
    invalid = (replace(Inputs(), dispatch=(Dispatch(),)), replace(Inputs(), dispatch=(Dispatch(flows=17),) * 8),
               replace(Inputs(), rob_head=RobPtr(value=160)), replace(Inputs(), addresses=(Address(slot=64), Address())),
               replace(Inputs(), queries=(Query(),)), replace(Inputs(), data=(Data(data=1 << 128), Data())),
               replace(Inputs(), second_pages=(SecondPage(sq=SqPtr(value=64)), SecondPage())))
    for inp in invalid:
        try:
            encode(inp)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid actual pin width/domain accepted")
    out = ROOT / "results/sq-codec-static-01"
    out.mkdir(exist_ok=False)
    files = (Path(__file__), ROOT / "lsqverify/store_queue/types.py", ROOT / "lsqverify/store_queue/decode.py", ROOT / "lsqverify/store_queue/ports.py",
             ROOT / "lsqverify/psq/types.py", ROOT / "lsqverify/psq/decode.py", ROOT / "lsqverify/vsq/types.py")
    hashes = {}
    for path in files:
        dest = out / "source" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[str(path.relative_to(ROOT))] = sha(dest)
    report = {"status": "static_actual_external_codec_verified_not_native_functional_ut", "inputs_excluding_clock": len(widths), "outputs": 338,
              "serialization_samples": 256, "invalid_rejected": len(invalid), "rtl_sha256": sha(source), "source_hashes": hashes,
              "limits": "Serialization includes inactive/illegal producer combinations; it is not a semantic/legality claim. All VSQ-to-PSQ and PSQ-to-VSQ wires remain internal and cannot be driven."}
    (out / "static-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
