"""ITTAGE reconstructs targets from the correct region and history context."""

from __future__ import annotations

import pytest

from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.coverage.catalog import ittage_region_context_coverage_model
from bpuverify.ittage.coverage.catalog import write_ittage_region_context_coverage
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.common.env.paths import REPO_ROOT


PC = 0x400F_FF00
REGION_WIDTH = 20
HISTORY_TARGETS = (
    (0, 0x4000_0120, "same_region"),
    (0b0100, 0x4010_0120, "next_region"),
    (0b1000, 0x3FF0_0120, "previous_region"),
)


@pytest.mark.feature("BPU-ITTAGE-014")
@pytest.mark.feature("BPU-ITTAGE-017")
async def test_same_pc_history_contexts_keep_three_target_regions(ittage_agent):
    coverage = ittage_region_context_coverage_model()
    await ittage_agent.reset()
    assert {target & ((1 << REGION_WIDTH) - 1) for _, target, _ in HISTORY_TARGETS} == {0x120}
    assert [target >> REGION_WIDTH for _, target, _ in HISTORY_TARGETS] == [0x400, 0x401, 0x3FF]

    for history, target, phase in HISTORY_TARGETS:
        cold = await ittage_agent.predict(PC, folded_history=history)
        assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1, (
            history, cold
        )
        await ittage_agent.train(IttageTraining(
            PC, POSITION, target, cold.meta, 1, folded_history=history
        ))
        observed = await ittage_agent.predict(PC, folded_history=history)
        assert (observed.hit, observed.target) == (1, target), (
            history, target, observed
        )
        assert observed.meta["providerTarget_addr"] == target
        coverage.sample({"phase": phase})

    # One PC and identical low target bits make an incorrect PC-region path
    # or cross-context pointer reuse visible in the full target comparison.
    order = (0, 1, 2, 2, 1, 0)
    transfers = [
        ittage_agent.submit_predict(PC, folded_history=HISTORY_TARGETS[index][0])
        for index in order
    ]
    await ittage_agent.drain_predictions()
    for transfer, index in zip(transfers, order, strict=True):
        observed = await transfer
        expected = HISTORY_TARGETS[index][1]
        assert (observed.hit, observed.target) == (1, expected), (
            transfer.accepted_event.tick, index, observed
        )
        assert observed.meta["providerTarget_addr"] == expected
    coverage.sample({"phase": "interleaved_contexts"})

    coverage.assert_coverage(100.0)
    write_ittage_region_context_coverage(coverage, REPO_ROOT)
