"""Near-overflow guard must not poison a later rollback and resumed stack."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ras.coverage.catalog import ras_overflow_recovery_coverage_model
from suites.frontend.bpu.ras.coverage.catalog import write_ras_overflow_recovery_coverage
from suites.frontend.bpu.ras.checker.assertions import expected_top
from suites.frontend.bpu.ras.checker.assertions import pop
from suites.frontend.bpu.ras.checker.assertions import push
from suites.frontend.bpu.ras.case.definitions import CallVector
from suites.frontend.bpu.ras.case.definitions import unique_calls
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-RAS-010")
async def test_near_overflow_guard_then_rollback_resumes_push_pop(ras_agent):
    coverage = ras_overflow_recovery_coverage_model()
    await ras_agent.reset()
    checkpoint = None
    accepted = 0
    calls = unique_calls()

    for index, vector in enumerate(calls):
        before = ras_agent.snapshot()
        after = await push(ras_agent, vector)
        if after.top != expected_top(vector):
            assert after == before
            break
        accepted += 1
        if index == 3:
            checkpoint = after
    else:
        pytest.fail("speculative queue never reached its near-overflow guard")

    assert checkpoint is not None
    assert 4 < accepted < len(calls)
    guarded = ras_agent.snapshot()
    assert guarded == before
    coverage.sample({"phase": "push_guarded"})

    for vector in calls[index + 1:index + 4]:
        assert await push(ras_agent, vector) == guarded
    assert await pop(ras_agent) == guarded
    coverage.sample({"phase": "pop_guarded"})

    restored = await ras_agent.restore(checkpoint.redirect_meta)
    assert restored.top == checkpoint.top
    coverage.sample({"phase": "rollback"})

    fresh = CallVector(0xA000_1000, 5)
    resumed = await push(ras_agent, fresh)
    assert resumed.top == expected_top(fresh)
    coverage.sample({"phase": "push_resumed"})

    after_pop = await pop(ras_agent)
    assert after_pop.top == checkpoint.top
    coverage.sample({"phase": "pop_resumed"})

    coverage.assert_coverage(100.0)
    write_ras_overflow_recovery_coverage(coverage, REPO_ROOT)
