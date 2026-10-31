import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Static input adapter audit only: not native execution or functional UT."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from suites.memblock.lsq.replay.codec import encode
from suites.memblock.lsq.replay.types import Enqueue, Inputs, Uop
from suites.memblock.lsq.raw.types import FtqPtr, SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    source = ucv_paths.soc_rtl_for(ROOT) / 'LoadQueueReplay.sv'
    ports = source.read_text().split(");", 1)[0]
    inputs = {}
    for high, low, name in re.findall(r"\binput\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)\s*[,\n]", ports):
        if name != "clock":
            inputs[name] = int(high) - int(low) + 1 if high else 1
    assert len(inputs) > 300
    samples = [Inputs()]
    uop = Uop(rob=RobPtr.encode(161, former=False), lq=QueuePtr.encode(239), sq=SqPtr.encode(255),
              ftq=FtqPtr(True, 63), offset=31, rvc=True, checkpoint=(1 << 64) - 1, operation=4095,
              destination=255, wait_sq=SqPtr.encode(128), strict=True, exceptions=(1 << 23) | (1 << 6))
    for cause in range(12):
        req = Enqueue(True, uop, (1 << 50) - 1, 65535, True, True, True, True, 7, False, True,
                      119, 15, SqPtr.encode(127), SqPtr.encode(191), True, True, 1 << cause, 15, True, True)
        samples.append(Inputs(enqueues=(req,) * 3))
        samples.append(Inputs(enqueues=(replace(req, replay_feedback=True),) * 3))
    for inp in samples:
        values = encode(inp)
        assert set(values) == set(inputs), {"missing": sorted(set(inputs) - set(values)), "extra": sorted(set(values) - set(inputs))}
        for name, width in inputs.items():
            assert 0 <= values[name] < 1 << width, (name, values[name], width)
    rejected = 0
    for req in (Enqueue(True, need_replay=True, causes=0), Enqueue(True, need_replay=True, causes=3),
                Enqueue(True, need_replay=True, causes=1 << 12), Enqueue(True, replay_feedback=True, slot=120),
                Enqueue(True, vaddr=1 << 50)):
        try:
            encode(Inputs(enqueues=(req, Enqueue(), Enqueue())))
        except ValueError:
            rejected += 1
    assert rejected == 5
    output = ROOT / "results/replay-codec-static-01"
    output.mkdir(exist_ok=False)
    files = (Path(__file__), ROOT / "replay/codec.py", ROOT / "replay/types.py", ROOT / "docs/contracts/load-queue-replay.md")
    digests = {}
    for path in files:
        dest = output / "verification-source" / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        digests[str(path.relative_to(ROOT))] = sha(dest)
    report = {"status": "static_adapter_checks_only", "native_executed": False, "functional_acceptance": "NOT_EVALUATED",
              "source": str(source), "source_sha256": sha(source), "actual_input_pins_excluding_clock": len(inputs),
              "valid_encoding_samples": len(samples), "rejected_domain_or_width_samples": rejected, "snapshot_files": digests,
              "limits": "exact declared input names and bit widths checked against original SV; no DUT tick, model comparison, output check or RTL coverage claimed"}
    (output / "static-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    audit()
