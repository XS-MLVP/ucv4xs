"""IfuPerfAnalysis: three-stage reason pipeline, blame injection and aging."""

from __future__ import annotations

import random

import pytest

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.model.perf import BTB_MISS
from suites.frontend.ifu.model.perf import FTQ_BITS
from suites.frontend.ifu.model.perf import ICACHE_MISS
from suites.frontend.ifu.model.perf import ITLB_MISS
from suites.frontend.ifu.model.perf import ITTAGE_MISS
from suites.frontend.ifu.model.perf import Inputs
from suites.frontend.ifu.model.perf import MEM_VIO
from suites.frontend.ifu.model.perf import OTHER_REDIRECT
from suites.frontend.ifu.model.perf import PerfModel
from suites.frontend.ifu.model.perf import RAS_MISS
from suites.frontend.ifu.model.perf import TAGE_MISS
from suites.frontend.ifu.model.perf import WIDTH


def mask(*bits: int) -> int:
    return sum(1 << bit for bit in bits)


def apply(harness, inputs: Inputs) -> None:
    harness.set(
        io_ifuPerfCtrl_ifuWbRedirect=inputs.ifu_wb_redirect,
        io_topdownIn_backendRedirectTopdown_backendRedirect=inputs.backend_redirect,
        io_topdownIn_backendRedirectTopdown_controlFlowRedirect=inputs.control_flow_redirect,
        io_topdownIn_backendRedirectTopdown_memoryViolationRedirect=inputs.memory_violation_redirect,
        io_topdownIn_backendRedirectTopdown_tageMissBubble=inputs.tage_miss,
        io_topdownIn_backendRedirectTopdown_ittageMissBubble=inputs.ittage_miss,
        io_topdownIn_backendRedirectTopdown_rasMissBubble=inputs.ras_miss,
        io_topdownIn_icacheTopdown_iCacheMissBubble=inputs.icache_miss,
        io_topdownIn_icacheTopdown_itlbMissBubble=inputs.itlb_miss,
    )
    for bit in FTQ_BITS:
        harness.set(**{P.io(f"topdownIn_ftqTopdown_reasons_{bit}"): (inputs.ftq_bits >> bit) & 1})


def observe(harness) -> int:
    value = 0
    for bit in range(WIDTH):
        value |= harness.read(P.io(f"topdownOut_topdown_reasons_{bit}")) << bit
    return value


def cycle(harness, model: PerfModel, inputs: Inputs, *,
          expected_override: int | None = None) -> int:
    apply(harness, inputs)
    harness.refresh()
    observed = observe(harness)
    expected = (expected_override if expected_override is not None else model.output())
    assert observed == expected, (
        f"expected {expected:#x}, observed {observed:#x}, stages {model.stages}")
    model.tick(inputs)
    harness.step(1)
    return observed


def start(harness) -> PerfModel:
    harness.reset()
    return PerfModel()


EMPTY = Inputs()


# ---------------------------------------------------------------------------
# Directed pipeline behavior
# ---------------------------------------------------------------------------
@pytest.mark.feature("IFU-PA-001")
@pytest.mark.feature("IFU-PA-007")
def test_reset_is_quiet_and_reasons_age_out(perf_analysis):
    model = start(perf_analysis)
    assert cycle(perf_analysis, model, EMPTY) == 0
    pattern = mask(*FTQ_BITS)
    assert cycle(perf_analysis, model, Inputs(ftq_bits=pattern)) == 0
    assert cycle(perf_analysis, model, EMPTY) == 0
    assert cycle(perf_analysis, model, EMPTY) == 0
    assert cycle(perf_analysis, model, EMPTY) == pattern
    assert cycle(perf_analysis, model, EMPTY) == 0
    assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-001")
def test_ftq_reason_pattern_is_preserved(perf_analysis):
    model = start(perf_analysis)
    for pattern in (mask(2), mask(3, 5), mask(6, 7, 8), mask(2, 9), mask(*FTQ_BITS)):
        cycle(perf_analysis, model, EMPTY)
        cycle(perf_analysis, model, EMPTY)
        cycle(perf_analysis, model, EMPTY)
        cycle(perf_analysis, model, Inputs(ftq_bits=pattern))
        for _ in range(2):
            assert cycle(perf_analysis, model, EMPTY) == 0
        assert cycle(perf_analysis, model, EMPTY) == pattern


@pytest.mark.feature("IFU-PA-002")
def test_icache_and_itlb_miss_bubbles_are_attributed(perf_analysis):
    for field, bit in (("icache_miss", ICACHE_MISS), ("itlb_miss", ITLB_MISS)):
        model = start(perf_analysis)
        cycle(perf_analysis, model, Inputs(**{field: 1}))
        assert cycle(perf_analysis, model, EMPTY) == 0
        # Only stage 1 is annotated, so the bubble is visible for one stage
        # at the output (not stretched like an all-stage override).
        assert cycle(perf_analysis, model, EMPTY) == mask(bit)
        assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-003")
def test_writeback_redirect_blames_btb_for_the_whole_window(perf_analysis):
    model = start(perf_analysis)
    cycle(perf_analysis, model, Inputs(ifu_wb_redirect=1))
    for _ in range(3):
        assert cycle(perf_analysis, model, EMPTY) == mask(BTB_MISS)
    assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-004")
def test_backend_control_redirect_overrides_predictor_blame(perf_analysis):
    model = start(perf_analysis)
    cycle(perf_analysis, model, Inputs(
        backend_redirect=1, control_flow_redirect=1, tage_miss=1, ittage_miss=1, ras_miss=1))
    expected = mask(TAGE_MISS, ITTAGE_MISS, RAS_MISS)
    for _ in range(3):
        assert cycle(perf_analysis, model, EMPTY) == expected
    assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-005")
def test_memory_violation_and_other_redirect_have_distinct_blame(perf_analysis):
    for inputs, bit in (
        (Inputs(backend_redirect=1, memory_violation_redirect=1), MEM_VIO),
        (Inputs(backend_redirect=1), OTHER_REDIRECT),
    ):
        model = start(perf_analysis)
        cycle(perf_analysis, model, inputs)
        for _ in range(3):
            assert cycle(perf_analysis, model, EMPTY) == mask(bit)
        assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-006")
def test_writeback_btb_blame_wins_over_backend_override(perf_analysis):
    model = start(perf_analysis)
    cycle(perf_analysis, model, Inputs(backend_redirect=1, control_flow_redirect=1,
                                      tage_miss=1, ifu_wb_redirect=1))
    expected = mask(TAGE_MISS, BTB_MISS)
    for _ in range(3):
        assert cycle(perf_analysis, model, EMPTY) == expected
    assert cycle(perf_analysis, model, EMPTY) == 0


@pytest.mark.feature("IFU-PA-006")
def test_backend_override_replaces_stage_blame_not_other_reasons(perf_analysis):
    # A reason already in flight survives the override unless the override
    # explicitly assigns that bit; only the predictor-class bits are replaced.
    model = start(perf_analysis)
    cycle(perf_analysis, model, Inputs(ftq_bits=mask(2)))
    cycle(perf_analysis, model, Inputs(ftq_bits=mask(2)))
    cycle(perf_analysis, model, Inputs(ftq_bits=mask(2),
                                      backend_redirect=1, control_flow_redirect=1,
                                      tage_miss=1))
    expected = mask(2, TAGE_MISS)
    for _ in range(3):
        assert cycle(perf_analysis, model, EMPTY) == expected
    assert cycle(perf_analysis, model, EMPTY) == 0


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
def test_random_reason_sequences_match_the_model(perf_analysis):
    rng = random.Random(0x9E2F)
    model = start(perf_analysis)
    for _ in range(600):
        cycle(perf_analysis, model, random_inputs(rng))
