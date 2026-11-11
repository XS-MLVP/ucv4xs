"""IfuPerfAnalysis: three-stage reason pipeline, blame injection and aging."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.testbenches.perf_analysis.model.perf import BTB_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import FTQ_BITS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import ICACHE_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import ITLB_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import ITTAGE_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import Inputs
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import MEM_VIO
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import OTHER_REDIRECT
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import RAS_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import TAGE_MISS
from suites.frontend.ifu.testbenches.perf_analysis.model.perf import WIDTH


def mask(*bits: int) -> int:
    return sum(1 << bit for bit in bits)


EMPTY = Inputs()


# ---------------------------------------------------------------------------
# Directed pipeline behavior
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-PA-001")
@pytest.mark.feature("IFU-PA-007")
async def test_reset_is_quiet_and_reasons_age_out(perf_analysis):
    await perf_analysis.reset()
    assert await perf_analysis.cycle(EMPTY) == 0
    pattern = mask(*FTQ_BITS)
    assert await perf_analysis.cycle(Inputs(ftq_bits=pattern)) == 0
    assert await perf_analysis.cycle(EMPTY) == 0
    assert await perf_analysis.cycle(EMPTY) == 0
    assert await perf_analysis.cycle(EMPTY) == pattern
    assert await perf_analysis.cycle(EMPTY) == 0
    assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-001")
async def test_ftq_reason_pattern_is_preserved(perf_analysis):
    await perf_analysis.reset()
    for pattern in (mask(2), mask(3, 5), mask(6, 7, 8), mask(2, 9), mask(*FTQ_BITS)):
        await perf_analysis.cycle(EMPTY)
        await perf_analysis.cycle(EMPTY)
        await perf_analysis.cycle(EMPTY)
        await perf_analysis.cycle(Inputs(ftq_bits=pattern))
        for _ in range(2):
            assert await perf_analysis.cycle(EMPTY) == 0
        assert await perf_analysis.cycle(EMPTY) == pattern


@pytest.mark.feature("IFU-PA-002")
async def test_icache_and_itlb_miss_bubbles_are_attributed(perf_analysis):
    for field, bit in (("icache_miss", ICACHE_MISS), ("itlb_miss", ITLB_MISS)):
        await perf_analysis.reset()
        await perf_analysis.cycle(Inputs(**{field: 1}))
        assert await perf_analysis.cycle(EMPTY) == 0
        # Only stage 1 is annotated, so the bubble is visible for one stage
        # at the output (not stretched like an all-stage override).
        assert await perf_analysis.cycle(EMPTY) == mask(bit)
        assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-003")
async def test_writeback_redirect_blames_btb_for_the_whole_window(perf_analysis):
    await perf_analysis.reset()
    await perf_analysis.cycle(Inputs(ifu_wb_redirect=1))
    for _ in range(3):
        assert await perf_analysis.cycle(EMPTY) == mask(BTB_MISS)
    assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-004")
async def test_backend_control_redirect_overrides_predictor_blame(perf_analysis):
    await perf_analysis.reset()
    await perf_analysis.cycle(Inputs(
        backend_redirect=1, control_flow_redirect=1, tage_miss=1, ittage_miss=1, ras_miss=1))
    expected = mask(TAGE_MISS, ITTAGE_MISS, RAS_MISS)
    for _ in range(3):
        assert await perf_analysis.cycle(EMPTY) == expected
    assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-005")
async def test_memory_violation_and_other_redirect_have_distinct_blame(perf_analysis):
    for inputs, bit in (
        (Inputs(backend_redirect=1, memory_violation_redirect=1), MEM_VIO),
        (Inputs(backend_redirect=1), OTHER_REDIRECT),
    ):
        await perf_analysis.reset()
        await perf_analysis.cycle(inputs)
        for _ in range(3):
            assert await perf_analysis.cycle(EMPTY) == mask(bit)
        assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-006")
async def test_writeback_btb_blame_wins_over_backend_override(perf_analysis):
    await perf_analysis.reset()
    await perf_analysis.cycle(Inputs(backend_redirect=1, control_flow_redirect=1,
                                      tage_miss=1, ifu_wb_redirect=1))
    expected = mask(TAGE_MISS, BTB_MISS)
    for _ in range(3):
        assert await perf_analysis.cycle(EMPTY) == expected
    assert await perf_analysis.cycle(EMPTY) == 0


@pytest.mark.feature("IFU-PA-006")
async def test_backend_override_replaces_stage_blame_not_other_reasons(perf_analysis):
    # A reason already in flight survives the override unless the override
    # explicitly assigns that bit; only the predictor-class bits are replaced.
    await perf_analysis.reset()
    await perf_analysis.cycle(Inputs(ftq_bits=mask(2)))
    await perf_analysis.cycle(Inputs(ftq_bits=mask(2)))
    await perf_analysis.cycle(Inputs(ftq_bits=mask(2),
                                      backend_redirect=1, control_flow_redirect=1,
                                      tage_miss=1))
    expected = mask(2, TAGE_MISS)
    for _ in range(3):
        assert await perf_analysis.cycle(EMPTY) == expected
    assert await perf_analysis.cycle(EMPTY) == 0


# ---------------------------------------------------------------------------
# Random comparison
# ---------------------------------------------------------------------------
def random_inputs(rng: random.Random) -> Inputs:
    return Inputs(
        ftq_bits=rng.getrandbits(WIDTH) & mask(*FTQ_BITS),
        icache_miss=int(rng.random() < 0.15),
        itlb_miss=int(rng.random() < 0.1),
        backend_redirect=int(rng.random() < 0.2),
        control_flow_redirect=int(rng.random() < 0.5),
        memory_violation_redirect=int(rng.random() < 0.5),
        tage_miss=int(rng.random() < 0.5),
        ittage_miss=int(rng.random() < 0.5),
        ras_miss=int(rng.random() < 0.5),
        ifu_wb_redirect=int(rng.random() < 0.15),
    )


@pytest.mark.feature("IFU-PA-001")
@pytest.mark.feature("IFU-PA-002")
@pytest.mark.feature("IFU-PA-003")
@pytest.mark.feature("IFU-PA-004")
@pytest.mark.feature("IFU-PA-005")
@pytest.mark.feature("IFU-PA-006")
@pytest.mark.feature("IFU-PA-007")
async def test_random_reason_sequences_match_the_model(perf_analysis):
    rng = random.Random(0x9E2F)
    await perf_analysis.reset()
    for _ in range(600):
        await perf_analysis.cycle(random_inputs(rng))
