"""Every field a functional point depends on must exist on the DUT port surface.

Semantics come from the ISA/protocol contract, design intent only from the Scala,
and the drivable/observable surface only from the generated DUT.  This gate
checks the third leg: if a contract-critical field is not on the port, the
functional point cannot be observed at all, and if a field the RTL *needs* is
absent the implementation is broken rather than merely unobserved.

`manifest/critical-fields.json` records both directions.  A declared-absent
field is a documented defect or trim; it re-opens automatically the moment the
port appears, so a baseline or upstream bump cannot silently keep an old
verdict.
"""
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.selftest

ROOT = __import__('suites.memblock.lsq', fromlist=['ROOT']).ROOT          # suites/memblock/lsq
MANIFEST = ROOT / "manifest/critical-fields.json"


def ports_of(dut):
    path = ROOT / "dut" / dut / "signals.json"
    if not path.exists():
        return None

    def walk(node, prefix=()):
        if "Pin" in node:
            yield "_".join(prefix)
        else:
            for key, child in node.items():
                if isinstance(child, dict):
                    yield from walk(child, (*prefix, key))

    return set(walk(json.loads(path.read_text())))


def entries():
    return json.loads(MANIFEST.read_text())["fields"]


def test_manifest_is_well_formed():
    fields = entries()
    assert len(fields) >= 15
    seen = set()
    for entry in fields:
        key = (entry["dut"], entry["field"])
        assert key not in seen, f"duplicate entry: {key}"
        seen.add(key)
        assert entry["expect"] in ("port", "absent"), entry
        assert entry.get("functional_point"), entry
        if entry["expect"] == "absent":
            assert entry.get("reason"), f"{key}: absent without a reason"
        else:
            assert entry.get("why"), f"{key}: present without an explanation"


def test_declared_present_fields_exist():
    for entry in entries():
        if entry["expect"] != "port":
            continue
        ports = ports_of(entry["dut"])
        assert ports is not None, entry["dut"]
        assert entry["field"] in ports, (
            f"{entry['dut']}.{entry['field']} is required by "
            f"{entry['functional_point']} but is not on the DUT port surface")


def test_declared_absent_fields_still_absent():
    """These are documented defects.  If one appears, re-adjudicate - do not relax."""
    for entry in entries():
        if entry["expect"] != "absent":
            continue
        ports = ports_of(entry["dut"])
        assert ports is not None, entry["dut"]
        assert entry["field"] not in ports, (
            f"{entry['dut']}.{entry['field']} now exists; the recorded reason was: "
            f"{entry['reason']}. Re-run the probe and update the matrix instead of "
            "silently keeping the old verdict")


def test_io_store_fault_defect_is_recorded_on_both_store_levels():
    absent = {(entry["dut"], entry["field"]) for entry in entries() if entry["expect"] == "absent"}
    for dut in ("physical_store_queue", "store_queue"):
        assert (dut, "io_toUncacheBuffer_resp_bits_nderr") in absent, dut


def test_wrapper_still_exposes_the_bus_error_bits():
    """The loss must be inside the store queue, not at the shared-bus boundary."""
    ports = ports_of("lsq_wrapper")
    for name in ("io_uncache_resp_bits_nderr", "io_uncache_resp_bits_error"):
        assert name in ports, name
