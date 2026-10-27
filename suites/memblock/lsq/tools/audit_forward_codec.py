import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Static domain/pin completeness evidence, explicitly NOT native functional UT."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lsqverify.forward.codec import encode
from lsqverify.forward.types import Inputs, Query, Store, Translation, SecondPage, byte_count
from lsqverify.raw.types import SqPtr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ucv_paths.soc_rtl_for(ROOT) / 'ForwardModule.sv'
    header = source.read_text().split(");", 1)[0]
    declarations = re.findall(r"^\s*(input|output)\s*(?:\[([^]]+)\]\s*)?(\w+)\s*[,\n]", header, re.M)
    widths = {}
    for direction, width, name in declarations:
        if direction == "input" and name != "clock":
            widths[name] = int(width.split(":")[0]) + 1 if width else 1
    assert len(widths) == 695 and sum(direction == "output" for direction, _, _ in declarations) == 129
    samples = [Inputs()]
    for lane in range(3):
        for size in range(8):
            queries = tuple(Query(True, (1 << 50) - 1, SqPtr.encode(255), size, True, True, SqPtr.encode(191)) if index == lane else Query() for index in range(3))
            samples.append(Inputs(queries, (Translation((1 << 48) - 1, True),) * 3,
                                  (Store(size, (1 << 50) - 1, (1 << 36) - 1, 65535, (1 << 128) - 1, 3, True, True, True, True),) * 64,
                                  (SecondPage(True, (1 << 48) - 1, SqPtr.encode(255)),) * 2, SqPtr.encode(255), SqPtr.encode(63)))
    for inp in samples:
        pins = encode(inp)
        assert set(pins) == set(widths) and all(0 <= value < 1 << widths[name] for name, value in pins.items())
    assert [byte_count(size) for size in range(8)] == [1, 2, 4, 8, 16, 16, 16, 16]
    invalid = (Inputs(queries=(Query(),)), Inputs(stores=(Store(),)),
               Inputs(queries=(Query(vaddr=1 << 50), Query(), Query())),
               Inputs(translations=(Translation(1 << 48), Translation(), Translation())),
               Inputs(stores=(Store(page=1 << 36),) * 64), Inputs(stores=(Store(data=1 << 128),) * 64),
               Inputs(dequeue=SqPtr(False, False, 64)), Inputs(stores=(Store(size=8),) * 64))
    for inp in invalid:
        try:
            encode(inp)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid static width/domain was not rejected")
    out = ROOT / "results/forward-codec-static-01"
    out.mkdir(exist_ok=False)
    hashes = {}
    for path in (Path(__file__), ROOT / "lsqverify/forward/types.py", ROOT / "lsqverify/forward/codec.py"):
        dest = out / "source" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[str(path.relative_to(ROOT))] = sha(dest)
    result = {"status": "static_public_codec_verified_not_native_ut", "rtl_sha256": sha(source), "inputs_excluding_clock": len(widths),
              "outputs": 129, "valid_samples": len(samples), "invalid_samples_rejected": len(invalid), "memory_size_bytes": [byte_count(i) for i in range(8)],
              "frozen_sources": hashes, "limits": "No DUT clock, fixture, reference, response check, functional checked or native coverage is established by this static audit."}
    (out / "static-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
