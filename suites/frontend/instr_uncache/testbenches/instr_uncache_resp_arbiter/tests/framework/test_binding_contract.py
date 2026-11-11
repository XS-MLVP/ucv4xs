"""InstrUncache response arbiter structural binding evidence."""

from __future__ import annotations

import pytest


@pytest.mark.feature("INC-ENV-001")
async def test_arbiter_binding_is_exactly_five_and_five(instr_uncache_resp_arbiter_agent):
    audit = instr_uncache_resp_arbiter_agent.audit()
    assert audit["top"] == "Arbiter1_InstrUncacheResp"
    assert set(audit["inputs"]) == {
        "in_valid", "in_data", "in_corrupt", "in_denied", "in_need_resend"}
    assert set(audit["outputs"]) == {
        "out_valid", "out_data", "out_corrupt", "out_denied", "out_need_resend"}
    assert audit["absent"] == {}
