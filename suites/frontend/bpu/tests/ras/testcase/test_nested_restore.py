"""A redirect to a middle RAS frame preserves the older LIFO chain."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ras.coverage.catalog import ras_nested_restore_coverage_model
from suites.frontend.bpu.ras.coverage.catalog import write_ras_nested_restore_coverage
from suites.frontend.bpu.ras.checker.assertions import expected_top
from suites.frontend.bpu.ras.checker.assertions import pop
from suites.frontend.bpu.ras.checker.assertions import push
from suites.frontend.bpu.ras.case.definitions import CALL_A
from suites.frontend.bpu.ras.case.definitions import CALL_B
from suites.frontend.bpu.ras.case.definitions import CALL_C
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-RAS-009")
async def test_redirect_to_middle_frame_keeps_older_lifo_chain(ras_agent):
    coverage = ras_nested_restore_coverage_model()
    await ras_agent.reset()
    empty = ras_agent.snapshot()
    assert len({expected_top(vector) for vector in (CALL_A, CALL_B, CALL_C)}) == 3

    first = await push(ras_agent, CALL_A)
    assert first.top == expected_top(CALL_A)
    coverage.sample({"phase": "push_a"})

    middle = await push(ras_agent, CALL_B)
    assert middle.top == expected_top(CALL_B)
    coverage.sample({"phase": "push_b"})

    newest = await push(ras_agent, CALL_C)
    assert newest.top == expected_top(CALL_C)
    coverage.sample({"phase": "push_c"})

    restored = await ras_agent.restore(middle.redirect_meta)
    assert restored.top == expected_top(CALL_B)
    coverage.sample({"phase": "restore_b"})

    after_b = await pop(ras_agent)
    assert after_b.top == expected_top(CALL_A)
    coverage.sample({"phase": "pop_b"})

    after_a = await pop(ras_agent)
    assert after_a.top == empty.top
    coverage.sample({"phase": "pop_a"})

    coverage.assert_coverage(100.0)
    write_ras_nested_restore_coverage(coverage, REPO_ROOT)
