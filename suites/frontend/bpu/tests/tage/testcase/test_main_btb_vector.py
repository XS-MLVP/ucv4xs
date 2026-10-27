"""TAGE provider and confidence follow each MainBTB slot across stages."""

from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.catalog import tage_vector_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_vector_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION


@pytest.mark.feature("BPU-TAGE-019")
async def test_late_main_btb_provider_slots_and_overlapped_lookups(tage_agent):
    coverage = tage_vector_coverage_model()

    for slot in (1, 2, 3):
        await tage_agent.reset()
        late_position = POSITION + 2 * slot
        branches = [TageBaseBranch(POSITION, 0)]
        branches.extend([None] * (slot - 1))
        branches.append(TageBaseBranch(late_position, 0))

        cold = await tage_agent.predict_branches(PC, branches)
        assert len(cold.metas) == len(cold.valids) == 4
        assert cold.metas[0]["hasProvider"] == cold.metas[slot]["hasProvider"] == 0
        assert cold.provider_counter_valids[0] == cold.provider_counter_valids[slot] == 0

        await tage_agent.train(TageTraining(PC, late_position, 1, 0, cold.metas[slot]))
        weak = await tage_agent.predict_branches(PC, branches)
        assert weak.metas[0]["hasProvider"] == 0
        assert weak.metas[slot]["hasProvider"] == 1
        assert weak.provider_counter_valids[slot] == 1

        # Strengthen the allocated provider with a correctly taken outcome.
        # The base direction is now taken, so this is not a new allocation.
        await tage_agent.train(
            TageTraining(PC, late_position, 1, 1, weak.metas[slot], mispredict=0)
        )
        observed = await tage_agent.predict_branches(PC, branches)
        assert observed.metas[0]["hasProvider"] == 0
        assert observed.provider_counter_valids[0] == 0
        assert observed.metas[slot]["hasProvider"] == 1
        assert observed.provider_counter_valids[slot] == 1
        assert (observed.valids[slot], observed.takens[slot]) == (1, 1), (
            slot, observed
        )
        coverage.sample({"provider_slot": slot, "association": "serial"})

    await tage_agent.reset()
    trained_branches = (TageBaseBranch(POSITION, 0), None, TageBaseBranch(POSITION + 4, 0))
    cold_branches = (TageBaseBranch(POSITION + 1, 0), None, None, TageBaseBranch(POSITION + 6, 0))
    cold = await tage_agent.predict_branches(PC, trained_branches)
    await tage_agent.train(TageTraining(PC, POSITION + 4, 1, 0, cold.metas[2]))
    weak = await tage_agent.predict_branches(PC, trained_branches)
    await tage_agent.train(TageTraining(PC, POSITION + 4, 1, 1, weak.metas[2], mispredict=0))

    # The trained slot carries a high-confidence base only in this phase;
    # a cold layout uses a distinct late position and baseConf=0.
    trained_confident = (
        TageBaseBranch(POSITION, 0), None,
        TageBaseBranch(POSITION + 4, 0, base_conf=1),
    )
    layouts = ((trained_confident, 2, 1, 1), (cold_branches, 3, 0, 0)) * 2
    transfers = [tage_agent.submit_predict_branches(PC, branches) for branches, *_ in layouts]
    await tage_agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(transfers), 2))
    for transfer, (branches, slot, provider, conf) in zip(transfers, layouts, strict=True):
        result = await transfer
        assert result.metas[0]["hasProvider"] == 0
        assert result.metas[slot]["hasProvider"] == provider, (branches, result)
        assert result.metas[slot]["altConf"] == conf, (branches, result)
        assert result.provider_counter_valids[slot] == provider
        if provider:
            assert (result.valids[slot], result.takens[slot]) == (1, 1)
    coverage.sample({"provider_slot": 2, "association": "overlap"})

    coverage.assert_coverage(100.0)
    write_tage_vector_coverage(coverage, REPO_ROOT)
