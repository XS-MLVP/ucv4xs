"""Distinguish in-flight S2/S3 RAS operations from a stable main-RAS top."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import CALL_B
from suites.frontend.bpu.uras.case.definitions import MAIN_TOP
from suites.frontend.bpu.uras.case.definitions import pending_s3_pop_cycles
from suites.frontend.bpu.uras.case.definitions import younger_s2_push_cycles


@pytest.mark.feature("BPU-URAS-012")
async def test_pending_s3_pop_invalidates_neutral_s1_and_s2_override(uras_agent):
    await uras_agent.reset()
    results = await uras_agent.stream(pending_s3_pop_cycles())

    assert results[1] == UrasResult(1, MAIN_TOP)
    assert results[4].usable == 0  # Neutral S1 observes the pending S3 pop.
    assert results[5].usable == 0  # Neutral S2 override also observes it.
    assert results[7] == UrasResult(1, MAIN_TOP)  # S3 fire releases the block.


@pytest.mark.feature("BPU-URAS-013")
async def test_young_s2_push_wins_over_older_s3_pop(uras_agent):
    await uras_agent.reset()
    results = await uras_agent.stream(younger_s2_push_cycles())

    assert results[3] == pushed(CALL_B)
    assert results[4] == pushed(CALL_B)  # Pending S2 push outranks S3 pop.
    assert results[5].usable == 0  # Once S2 clears, older S3 pop is visible.
    assert results[7] == UrasResult(1, MAIN_TOP)
