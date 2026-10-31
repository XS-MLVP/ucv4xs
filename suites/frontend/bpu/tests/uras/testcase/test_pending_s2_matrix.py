"""S1 pop/neutral × pending S2 push/pop priority matrix."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.coverage.catalog import uras_pending_s2_coverage_model
from suites.frontend.bpu.uras.coverage.catalog import write_uras_pending_s2_coverage
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import CALL_A
from suites.frontend.bpu.uras.case.definitions import MAIN_TOP
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-URAS-014")
async def test_s1_action_against_pending_s2_operation(uras_agent):
    coverage = uras_pending_s2_coverage_model()
    main = UrasResult(1, MAIN_TOP)
    invalid = UrasResult(0, 0)
    scenarios = (
        ("push_pop", 2, 1, pushed(CALL_A), main, invalid),
        ("push_neutral", 2, 0, pushed(CALL_A), pushed(CALL_A), main),
        ("pop_pop", 1, 1, invalid, invalid, invalid),
        ("pop_neutral", 1, 0, invalid, invalid, main),
    )
    for name, older, younger, older_result, paired_result, next_result in scenarios:
        await uras_agent.reset()
        results = await uras_agent.stream((
            UrasCycle(
                s1_fire=1,
                spec_action=older,
                spec_start_pc=CALL_A.start_pc,
                spec_position=CALL_A.position,
                full_ret_addr=MAIN_TOP,
            ),
            UrasCycle(s1_fire=1, spec_action=younger, full_ret_addr=MAIN_TOP),
            UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
            UrasCycle(),
        ))
        # stream's first response belongs to the pre-launch cycle; the next
        # three resolve the older op, pair it with S1, and advance S1 again.
        assert results == (invalid, older_result, paired_result, next_result), name
        coverage.sample({"pairing": name, "usable": paired_result.usable})

    coverage.assert_coverage(100.0)
    write_uras_pending_s2_coverage(coverage, REPO_ROOT)
