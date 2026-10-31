"""Neutral corrections cancel younger speculation and recover the main top."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.coverage.catalog import uras_neutral_override_coverage_model
from suites.frontend.bpu.uras.coverage.catalog import write_uras_neutral_override_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import CALL_A
from suites.frontend.bpu.uras.case.definitions import CALL_B
from suites.frontend.bpu.uras.case.definitions import MAIN_TOP


def neutral_override(stage, target):
    """Competing younger calls must lose even to a no-action correction."""
    return UrasCycle(
        s1_fire=1, spec_action=2,
        spec_start_pc=CALL_B.start_pc, spec_position=CALL_B.position,
        s2_valid=1, s2_action=0 if stage == 2 else 2,
        s2_start_pc=CALL_B.start_pc, s2_position=CALL_B.position,
        s3_valid=int(stage == 3), s3_action=0,
        full_ret_addr=target,
    )


@pytest.mark.feature("BPU-URAS-015")
async def test_neutral_overrides_restore_current_main_top_and_cancel_younger_calls(uras_agent):
    coverage = uras_neutral_override_coverage_model()
    for stage in (2, 3):
        await uras_agent.reset()
        assert await uras_agent.cycle(
            UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP)
        ) == UrasResult(1, MAIN_TOP)

        target = MAIN_TOP + 0x102 * stage
        correction = neutral_override(stage, target)
        assert await uras_agent.cycle(correction) == UrasResult(1, target)
        coverage.sample({"stage": stage, "phase": "quiescent"})

        assert await uras_agent.cycle(UrasCycle(
            s1_fire=1, spec_action=2,
            spec_start_pc=CALL_A.start_pc, spec_position=CALL_A.position,
        )) == pushed(CALL_A)
        target += 0x204
        correction = neutral_override(stage, target)
        assert await uras_agent.cycle(correction) == UrasResult(1, target)
        coverage.sample({"stage": stage, "phase": "cancel_call"})
        assert await uras_agent.cycle(UrasCycle()) == UrasResult(1, target)

        # Redirect dominates both correction stages and flushes pending calls.
        for _ in range(2):
            observed = await uras_agent.cycle(replace(correction, has_redirect=1))
            assert observed.usable == 0, (stage, observed)
        coverage.sample({"stage": stage, "phase": "redirect_priority"})

        target += 0x408
        correction = neutral_override(stage, target)
        observed = await uras_agent.cycle(correction)
        if stage == 2:
            # Unlike S3's direct main-RAS path, neutral S2 honors redirectDelay1.
            assert observed == UrasResult(0, 0), observed
        else:
            assert observed == UrasResult(1, target), observed
        assert await uras_agent.cycle(correction) == UrasResult(1, target)
        coverage.sample({"stage": stage, "phase": "redirect_recovery"})

        # Withdraw the corrections; cancelled younger calls must not reappear.
        for _ in range(2):
            assert await uras_agent.cycle(UrasCycle()) == UrasResult(1, target)
        coverage.sample({"stage": stage, "phase": "stable_next"})
    coverage.assert_coverage(100.0)
    write_uras_neutral_override_coverage(coverage, REPO_ROOT)
