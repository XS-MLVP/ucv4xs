"""Real concurrent prediction reads defer four independent target-table writes."""

from __future__ import annotations

from functools import partial

import pytest

from bpuverify.ittage.transaction.types import IttageBatchTraining
from bpuverify.ittage.transaction.types import IttageBranchFeedback
from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.coverage.catalog import ittage_pending_feedback_coverage_model
from bpuverify.ittage.coverage.catalog import write_ittage_pending_feedback_coverage
from bpuverify.ittage.checker.assertions import prepare_first_provider
from bpuverify.ittage.checker.assertions import prepare_null_highest_provider
from bpuverify.ittage.checker.assertions import require_snapshot
from bpuverify.ittage.case.definitions import HIGHEST_TABLE
from bpuverify.ittage.case.definitions import PENDING_TARGETS
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.case.definitions import SAME_BANK_PCS
from bpuverify.common.env.paths import REPO_ROOT


async def check_pending_mode(agent, coverage, *, mode: str, bank: int, overlap: bool):
    await agent.reset()
    # Byte PC bit 1 selects the ITTAGE bank. Halfword-aligned fetch starts
    # must work in both banks; bit 2 independently selects a folded SRAM lane.
    pcs = tuple(pc + 2 * bank for pc in SAME_BANK_PCS)
    residents = [
        await prepare_first_provider(agent, pc=pc, position=POSITION, target=target)
        if mode == "first" else
        await prepare_null_highest_provider(agent, pc=pc, position=POSITION)
        for pc, target in zip(pcs, PENDING_TARGETS)
    ]
    table = 0 if mode == "first" else HIGHEST_TABLE
    for index, prediction in enumerate(residents):
        assert prediction.meta["provider"] == {"bits": table, "valid": 1}, prediction
        assert prediction.meta["providerCnt_value"] == (2 if mode == "first" else 0), prediction
        if overlap:
            coverage.sample({"phase": "overlap_resident", "mode": mode, "bank": bank, "context": index})

    feedback = tuple(
        IttageBatchTraining(pc, prediction.meta, (
            IttageBranchFeedback(POSITION, target, taken=1, mispredict=int(prediction.target != target)),
        ))
        for pc, target, prediction in zip(pcs, PENDING_TARGETS, residents)
    )
    transfers = []
    if overlap:
        transfers = [
            agent.submit_predict(pc, expected=partial(require_snapshot, expected=resident))
            for _ in range(4)
            for pc, resident in zip(pcs, residents)
        ]
    # Replay the same four observed metadata snapshots, not invented newer
    # counters. Only four distinct indices are pending; the second pass also
    # revisits any context whose first write retired during read startup.
    event = await agent.train_batches(feedback * 2, overlap_predictions=overlap)
    if overlap:
        # This fails if training is serialized after the prediction stream.
        assert transfers[0].accepted_event.tick <= event.tick < transfers[-1].accepted_event.tick
        for index, transfer in enumerate(transfers):
            require_snapshot(await transfer, residents[index % 4])
            coverage.sample({"phase": "overlap_pending_read", "mode": mode, "bank": bank, "context": index % 4})

    drained = [await agent.predict(pc) for pc in pcs]
    drive = "overlap" if overlap else "serial"
    for index, (prediction, target) in enumerate(zip(drained, PENDING_TARGETS)):
        assert prediction.hit == 1, prediction
        assert prediction.meta["provider"] == {"bits": table, "valid": 1}, prediction
        assert prediction.meta["providerCnt_value"] == (3 if mode == "first" else 0), prediction
        assert prediction.meta["providerTarget_addr"] == target, prediction
        if mode == "first":
            assert prediction.target == target, prediction
        else:
            selected = prediction.meta["altProviderTarget_addr"] if prediction.meta["altProvider"]["valid"] else target
            assert prediction.target == selected, prediction
        coverage.sample({"phase": f"{drive}_drained", "mode": mode, "bank": bank, "context": index})

    # Update clean shadows one at a time after the burst. A first-table miss
    # allocates its real offered longer provider and decrements the original
    # alternate; a highest-table correct feedback strengthens the new target.
    expected = list(drained)
    for index, (pc, target, before) in enumerate(zip(pcs, PENDING_TARGETS, drained)):
        new_target = target + 0x400 if mode == "first" else target
        await agent.train(IttageTraining(pc, POSITION, new_target, before.meta, int(before.target != new_target)))
        actual = await agent.predict(pc)
        assert (actual.hit, actual.target) == (1, new_target), actual
        if mode == "first":
            assert before.meta["allocate"]["valid"] == 1, before
            assert actual.meta["provider"]["bits"] == before.meta["allocate"]["bits"], (before, actual)
            assert actual.meta["providerCnt_value"] == 2, actual
            assert actual.meta["altProvider"] == {"bits": 0, "valid": 1}, actual
            assert actual.meta["altProviderCnt_value"] == 2, actual
            assert actual.meta["altProviderTarget_addr"] == target, actual
        else:
            assert actual.meta["provider"] == {"bits": HIGHEST_TABLE, "valid": 1}, actual
            assert actual.meta["providerCnt_value"] == 1, actual
        expected[index] = actual
        for neighbor_pc, snapshot in zip(pcs, expected):
            require_snapshot(await agent.predict(neighbor_pc), snapshot)
        coverage.sample({"phase": f"{drive}_retrained", "mode": mode, "bank": bank, "context": index})
    # Allocation may choose different legal tables at different LFSR ticks;
    # compare functional target/confidence roles rather than literal new IDs.
    return tuple((p.target, p.meta["providerCnt_value"], p.meta["altProviderCnt_value"] if mode == "first" else None) for p in expected)


@pytest.mark.feature("BPU-ITTAGE-016")
async def test_four_pending_indices_survive_live_same_bank_predictions(ittage_agent):
    coverage = ittage_pending_feedback_coverage_model()
    for bank in range(2):
        for mode in ("first", "highest"):
            overlapped = await check_pending_mode(ittage_agent, coverage, mode=mode, bank=bank, overlap=True)
            serial = await check_pending_mode(ittage_agent, coverage, mode=mode, bank=bank, overlap=False)
            assert serial == overlapped
    coverage.assert_coverage(100.0)
    write_ittage_pending_feedback_coverage(coverage, REPO_ROOT)
