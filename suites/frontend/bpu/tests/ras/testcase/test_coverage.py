"""Dedicated RAS functional-coverage closure scenario."""

from __future__ import annotations
import pytest

from bpuverify.ras.coverage.catalog import ras_coverage_model
from bpuverify.ras.coverage.catalog import write_ras_coverage
from bpuverify.ras.checker.assertions import expected_top
from bpuverify.ras.checker.assertions import pop
from bpuverify.ras.checker.assertions import push
from bpuverify.ras.case.definitions import CALL_A
from bpuverify.ras.case.definitions import CALL_B
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-RAS-008')
async def test_ras_functional_coverage_closes_defined_bins(ras_agent):
    coverage = ras_coverage_model()
    await ras_agent.reset()
    initial = ras_agent.snapshot()
    empty = await pop(ras_agent)
    assert empty.top == initial.top
    coverage.sample({"operation": "pop", "stack_shape": "empty"})

    first = await push(ras_agent, CALL_A)
    assert first.top == expected_top(CALL_A)
    coverage.sample({"operation": "push", "stack_shape": "unique"})
    saved = first
    repeated = await push(ras_agent, CALL_A)
    assert repeated.top == expected_top(CALL_A)
    assert repeated.redirect_meta["sctr"] == saved.redirect_meta["sctr"] + 1
    coverage.sample({"operation": "push", "stack_shape": "repeated"})
    after_pop = await pop(ras_agent)
    assert after_pop.top == expected_top(CALL_A)
    assert after_pop.redirect_meta["sctr"] == saved.redirect_meta["sctr"]
    coverage.sample({"operation": "pop", "stack_shape": "repeated"})
    restored = await ras_agent.restore(saved.redirect_meta)
    assert restored.top == expected_top(CALL_A)
    coverage.sample({"operation": "redirect", "stack_shape": "unique"})
    empty_again = await ras_agent.restore(initial.redirect_meta)
    assert empty_again.top == initial.top
    disabled = await push(ras_agent, CALL_B, enable=0)
    assert disabled.top == initial.top
    assert disabled.redirect_meta == empty_again.redirect_meta
    assert disabled.commit_meta == empty_again.commit_meta
    coverage.sample({"operation": "disabled_top_held", "stack_shape": "empty"})

    coverage.assert_coverage(100.0)
    write_ras_coverage(coverage, REPO_ROOT)
