"""Committed frames remain usable after their speculative entries retire."""

from __future__ import annotations

import pytest

from bpuverify.ras.coverage.catalog import ras_commit_recovery_coverage_model
from bpuverify.ras.coverage.catalog import write_ras_commit_recovery_coverage
from bpuverify.ras.checker.assertions import committed_round_trips
from bpuverify.ras.checker.assertions import expected_top
from bpuverify.ras.checker.assertions import pop
from bpuverify.ras.checker.assertions import push
from bpuverify.ras.case.definitions import CALL_A
from bpuverify.ras.case.definitions import CALL_B
from bpuverify.ras.case.definitions import CALL_C
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-RAS-011")
async def test_returns_recover_committed_frames_after_speculative_retirement(ras_agent):
    coverage = ras_commit_recovery_coverage_model()
    await ras_agent.reset()
    initial = ras_agent.snapshot()

    for name, call in (("a", CALL_A), ("b", CALL_B), ("c", CALL_C)):
        before = ras_agent.snapshot()
        pushed = await push(ras_agent, call)
        assert pushed.top == expected_top(call)
        committed = await ras_agent.commit(before.commit_meta, action=2)
        assert committed.top == expected_top(call)
        assert committed.commit_meta == pushed.commit_meta
        coverage.sample({"phase": f"commit_{name}"})

    # Committing C advances the speculative queue's retirement boundary past
    # A and B. The next returns must obtain those older addresses from the
    # committed stack rather than still-live speculative entries.
    checkpoint = ras_agent.snapshot()
    recycled = await committed_round_trips(ras_agent, resident_top=expected_top(CALL_C))
    assert recycled.commit_meta["tosw"]["flag"] != checkpoint.commit_meta["tosw"]["flag"]
    coverage.sample({"phase": "queue_reused"})

    for phase, expected in (
        ("return_c_to_b", expected_top(CALL_B)),
        ("return_b_to_a", expected_top(CALL_A)),
        ("return_a_to_empty", initial.top),
    ):
        before = ras_agent.snapshot()
        returned = await pop(ras_agent)
        assert returned.top == expected
        committed = await ras_agent.commit(before.commit_meta, action=1)
        assert committed.top == expected
        assert committed.commit_meta == returned.commit_meta
        coverage.sample({"phase": phase})

    coverage.assert_coverage(100.0)
    write_ras_commit_recovery_coverage(coverage, REPO_ROOT)
