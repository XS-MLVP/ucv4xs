"""In a settled single-PC stream, both MicroTAGE sideband phases agree."""

from __future__ import annotations

import pytest

from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import CONDITIONAL


@pytest.mark.feature("BPU-ABTB-007")
async def test_metadata_and_microtage_sideband_match_prediction(abtb_agent):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(CONDITIONAL.pc)
    await train_taken(abtb_agent, CONDITIONAL, cold.meta)
    prediction = await abtb_agent.predict(CONDITIONAL.pc)
    index, entry = matching_entry(
        prediction, CONDITIONAL.position, CONDITIONAL.branch_type
    )

    assert prediction.meta["valid"] == 1
    assert prediction.meta["entries"][index]["hit"] == 1
    sideband = prediction.micro_tage
    assert sideband["fastPositions"][index] == CONDITIONAL.position
    assert sideband["result"][index]["valid"] == entry.valid
    assert sideband["result"][index]["bits"]["taken"] == entry.taken
    assert (
        sideband["result"][index]["bits"]["cfiPosition"]
        == entry.position
    )
    assert (
        sideband["result"][index]["bits"]["attribute"]["branchType"]
        == entry.branch_type
    )
