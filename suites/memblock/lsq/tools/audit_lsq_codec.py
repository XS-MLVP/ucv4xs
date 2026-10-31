#!/usr/bin/env python3
"""Static complete wrapper pin binding/roundtrip, NOT native functional tests."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from suites.memblock.lsq.lsq_wrapper.codec import encode, ports
from suites.memblock.lsq.lsq_wrapper.ports import decode
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    widths, rng = ports()["input"], random.Random(20261018)
    seen = {name: set() for name in widths}
    assert encode(decode(encode(Inputs()))) == encode(Inputs())
    for _ in range(256):
        pins = {}
        for pin, width in widths.items():
            limit = 1 << width
            if pin.endswith("robIdx_value") or pin.endswith(("pendingPtr_value", "pendingPtrNext_value")):
                limit = 160
            elif pin.endswith("lqIdx_value"):
                limit = 120
            elif pin.endswith("numLsElem"):
                limit = 17
            elif pin.endswith("schedIndex"):
                limit = 120
            pins[pin] = rng.randrange(limit)
        for lane in range(3):
            p = f"io_ldu_ldin_{lane}_"
            if pins[p + "valid"] and pins[p + "bits_rep_info_need_rep"]:
                cause = rng.randrange(12)
                for bit in range(13):
                    pins[p + f"bits_rep_info_cause_{bit}"] = int(bit == cause)
        packet = decode(pins)
        actual = encode(packet)
        assert actual == pins, {pin: (pins[pin], actual.get(pin)) for pin in pins if actual.get(pin) != pins[pin]}
        for pin, value in pins.items():
            seen[pin].add(value)
    assert all(len(values) >= 2 for values in seen.values())
    rejected = []
    def reject(label, packet):
        try:
            encode(packet)
        except (AssertionError, TypeError, ValueError):
            rejected.append(label)
        else:
            raise AssertionError(("invalid adapter packet accepted", label))
    reject("wrong_dispatch_width", replace(Inputs(), dispatch=(Dispatch(),)))
    reject("wrong_load_width", replace(Inputs(), loads=()))
    reject("wrong_store_width", replace(Inputs(), addresses=(Address(),)))
    reject("flow_17", replace(Inputs(), dispatch=(Dispatch(flows=17),) + (Dispatch(),) * 7))
    reject("need_alloc_4", replace(Inputs(), dispatch=(Dispatch(need_alloc=4),) + (Dispatch(),) * 7))
    reject("load_index_120", replace(Inputs(), dispatch=(Dispatch(load_start=QueuePtr(False, 120)),) + (Dispatch(),) * 7))
    reject("rob_index_160", replace(Inputs(), pending=RobPtr(False, 160, True)))
    reject("sq_index_64", replace(Inputs(), data=(Data(sq=SqPtr(False, False, 64)), Data())))
    reject("data_129_bits", replace(Inputs(), data=(Data(data=1 << 128), Data())))
    reject("sta_paddr_49_bits", replace(Inputs(), addresses=(Address(paddr=1 << 48), Address())))
    reject("bus_mid_128", replace(Inputs(), bus=Bus(mid=128)))
    fake = []
    for name in ("address_ready", "address_bits", "data_ready", "data_bits", "dequeue", "upper", "sq_empty", "ld_wb_ptr",
                 "rar_full", "raw_full", "mmio_wake", "nc_wake", "precommit", "retired"):
        try:
            Inputs(**{name: 1})
        except TypeError:
            fake.append(name)
        else:
            raise AssertionError(("fake internal control became a wrapper input", name))
    contract = ROOT / "docs/contracts/lsq-wrapper.md"
    catalog = {}
    for line in contract.read_text().splitlines():
        if line.startswith("| LSQ-"):
            _, group, cases, *_ = line.split("|")
            catalog[group.strip()] = [case.strip() for case in cases.split("/")]
    assert sum(map(len, catalog.values())) == 82
    source_record = json.loads((ROOT / "rtl/lsq_wrapper/source.json").read_text())
    assert len(source_record["files"]) == 53
    assert source_record["files"]["LsqWrapper.sv"] == "7833f0083df200ecdc3f4be2c0821eb91131bb415666befb65d7abe92b550b65"
    assert all(sha(ROOT / "rtl/lsq_wrapper" / path) == digest for path, digest in source_record["files"].items())
    files = [Path(__file__), contract, ROOT / "manifest/duts.json", ROOT / "rtl/lsq_wrapper/source.json"]
    for family in ("lsq_wrapper", "load_queue", "store_queue", "psq", "replay"):
        files.extend(path for path in (ROOT / family).glob("*.py") if path.name in ("types.py", "codec.py", "ports.py"))
    dest = ROOT / "results/static/lsq-wrapper-codec-v1"
    report = dict(status="static_adapter_roundtrip_only_not_native_functional_acceptance", seed=20261018,
                  public_inputs=603, public_outputs=458, random_packets=256, varied_inputs=len(seen),
                  invalid_packets_rejected=rejected, fake_internal_controls_rejected=fake, pretest_catalog=catalog,
                  pretest_scenarios=82, rtl_closure_files=53,
                  source_sha256={str(path.relative_to(ROOT)): sha(path) for path in sorted(set(files))},
                  limits="Pure adapter random packets are NOT legal mixed traffic or DUT coverage. No reference model or fixture yet. Defaults used only to construct discarded child adapter fields; none is a writable wrapper internal-feedback input. Native functional checks, fair drain and RTL coverage iterations still required.")
    out = dest / "report.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        dest.mkdir(parents=True, exist_ok=False)
        for path in files:
            frozen = dest / "source" / path.relative_to(ROOT)
            frozen.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, frozen)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("source_sha256", "pretest_catalog")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    audit()
