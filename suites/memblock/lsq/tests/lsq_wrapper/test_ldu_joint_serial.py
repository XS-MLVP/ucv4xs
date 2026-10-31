"""Own uncovered serial pendingstate lines, with original effects completed."""

from dataclasses import replace

import pytest

from .ldu_joint_owners import LduJointOwners

from suites.memblock.lsq.legacy_pins import P


class SerialOwners(LduJointOwners):
    def external(self, **options):
        return replace(super().external(**options), outstanding=False)


@pytest.mark.parametrize("kind", ("nc_load", "mmio_load", P.p_load, "nc_store", P.p_store))
@pytest.mark.parametrize("lane", range(3))
async def test_source_LDU_serial_original_bus_owner_response_and_younger_cached_completion(lsq, kind, lane):
    trace = SerialOwners(lsq, 0x7410+lane)
    trace.rounds, trace.launch_cursor = lane%2, lane
    await trace.cycle(allocate=(kind,))
    original = trace.history[-1]
    await trace.fair_drain()
    assert original["complete"] and original["retired"] and len(original["attempts"]) == 1
    job = original["attempts"][0]
    assert job["sid"] is not None and job["response"] is not None
    if original["kind"] == "load":assert job["consumed"]
    elif kind == P.p_store:assert original["wb"] is not None
    await trace.cycle(allocate=("cached",))
    await trace.fair_drain()
    assert len(trace.history) == 2 and all(s["complete"] and s["retired"] for s in trace.history)
    lsq.emit("LDU_serial_original_and_younger_fully_complete", kind=kind, lane=lane, original_UID=original["uid"],
             external_job=job["uid"], real_response=True, source_S3=True, only_supplemental_serial_gap=True)
