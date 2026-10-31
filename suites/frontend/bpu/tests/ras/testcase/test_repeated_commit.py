"""Committed duplicate counters survive queue reuse and do not wrap at max."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ras.coverage.catalog import ras_repeated_commit_coverage_model
from suites.frontend.bpu.ras.coverage.catalog import write_ras_repeated_commit_coverage
from suites.frontend.bpu.ras.checker.assertions import committed_round_trips
from suites.frontend.bpu.ras.checker.assertions import expected_top
from suites.frontend.bpu.ras.checker.assertions import pop
from suites.frontend.bpu.ras.checker.assertions import push
from suites.frontend.bpu.ras.case.definitions import CALL_A
from suites.frontend.bpu.ras.case.definitions import CALL_B
from suites.frontend.bpu.ras.case.definitions import STACK_COUNTER_MAX
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-RAS-012")
async def test_committed_repeats_unwind_after_queue_reuse_and_counter_saturation(ras_agent):
    coverage = ras_repeated_commit_coverage_model()
    for mode, repetitions in (("normal", 3), ("saturated", STACK_COUNTER_MAX + 2)):
        await ras_agent.reset()
        initial = ras_agent.snapshot()
        assert (await push(ras_agent, CALL_A)).top == expected_top(CALL_A)
        assert (await ras_agent.commit(initial.commit_meta, action=2)).top == expected_top(CALL_A)

        for index in range(repetitions):
            before = ras_agent.snapshot()
            pushed = await push(ras_agent, CALL_B)
            assert pushed.top == expected_top(CALL_B)
            assert pushed.redirect_meta["sctr"] == index % (STACK_COUNTER_MAX + 1)
            assert (await ras_agent.commit(before.commit_meta, action=2)).top == expected_top(CALL_B)
        coverage.sample({"phase": f"{mode}_pushes"})

        # Force the old duplicate frames out of the speculative queue. Their
        # counters must now come from the committed stack, not spec-only state.
        await committed_round_trips(ras_agent, resident_top=expected_top(CALL_B))
        for index in range(repetitions):
            before = ras_agent.snapshot()
            returned = await pop(ras_agent)
            remaining = repetitions - index - 1
            expected = expected_top(CALL_B if remaining else CALL_A)
            assert returned.top == expected
            assert returned.redirect_meta["sctr"] == (
                (remaining - 1) % (STACK_COUNTER_MAX + 1) if remaining else 0
            )
            assert (await ras_agent.commit(before.commit_meta, action=1)).top == expected
        coverage.sample({"phase": f"{mode}_returns"})

        before = ras_agent.snapshot()
        assert (await pop(ras_agent)).top == initial.top
        assert (await ras_agent.commit(before.commit_meta, action=1)).top == initial.top
        coverage.sample({"phase": f"{mode}_empty"})

    coverage.assert_coverage(100.0)
    write_ras_repeated_commit_coverage(coverage, REPO_ROOT)
