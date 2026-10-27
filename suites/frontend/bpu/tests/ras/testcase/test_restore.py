"""RAS redirect recovery and enable gate."""

from __future__ import annotations

import pytest

from bpuverify.ras.coverage.catalog import ras_enable_integrity_coverage_model
from bpuverify.ras.coverage.catalog import write_ras_enable_integrity_coverage
from bpuverify.ras.checker.assertions import expected_top
from bpuverify.ras.checker.assertions import pop
from bpuverify.ras.checker.assertions import push
from bpuverify.ras.case.definitions import CALL_A
from bpuverify.ras.case.definitions import CALL_B
from bpuverify.ras.case.definitions import unique_calls
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-RAS-007")
async def test_redirect_metadata_restores_saved_stack(ras_agent):
    await ras_agent.reset()
    await push(ras_agent, CALL_A)
    saved = ras_agent.snapshot()
    await push(ras_agent, CALL_B)

    restored = await ras_agent.restore(saved.redirect_meta)
    assert restored.top == expected_top(CALL_A)


@pytest.mark.feature("BPU-RAS-007")
async def test_restore_checkpoint_whose_stack_pointer_already_wrapped(ras_agent):
    """A nine-call checkpoint has a wrapped three-bit stack pointer.

    Restoring it after three younger calls must recover the ninth call as the
    top, and every older return address must unwind in order. The wrapped
    pointer is genuine hardware state, not a hand-built metadata value.
    """

    calls = unique_calls()[:12]
    await ras_agent.reset()
    initial = ras_agent.snapshot()
    for call in calls[:9]:
        await push(ras_agent, call)
    saved = ras_agent.snapshot()
    assert saved.redirect_meta["ssp"] < 8
    for call in calls[9:12]:
        await push(ras_agent, call)

    restored = await ras_agent.restore(saved.redirect_meta)
    assert restored.top == expected_top(calls[8])
    for call in reversed(calls[:8]):
        assert (await pop(ras_agent)).top == expected_top(call)
    assert (await pop(ras_agent)).top == initial.top


@pytest.mark.feature("BPU-RAS-008")
@pytest.mark.rtl_defect
@pytest.mark.xfail(
    reason=(
        "RTL defect: Ras gates stack.spec.fire with enable but leaves "
        "spec.pushValid/popValid asserted, so disabled actions corrupt pointers"
    ),
    strict=True,
)
async def test_disable_gate_preserves_stack(ras_agent):
    coverage = ras_enable_integrity_coverage_model()
    await ras_agent.reset()
    await push(ras_agent, CALL_A)
    before = ras_agent.snapshot()

    disabled = await push(ras_agent, CALL_B, enable=0)
    assert disabled.top == before.top
    coverage.sample({"phase": "top_preserved"})
    after = ras_agent.snapshot()
    if after.redirect_meta != before.redirect_meta:
        write_ras_enable_integrity_coverage(coverage, REPO_ROOT)
        raise AssertionError(
            "disabled RAS action changed redirect metadata: "
            f"before={before.redirect_meta!r}, after={after.redirect_meta!r}"
        )
    coverage.sample({"phase": "metadata_preserved"})
    coverage.assert_coverage(100.0)
    write_ras_enable_integrity_coverage(coverage, REPO_ROOT)
