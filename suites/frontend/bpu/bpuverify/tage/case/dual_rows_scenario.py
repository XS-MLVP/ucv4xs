"""Dual-way feedback at four pending indices, using public agent transactions."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TagePrediction
from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.checker.assertions import fill_useful_set
from bpuverify.tage.case.definitions import HIGHEST_TABLE
from bpuverify.tage.case.definitions import SAME_BANK_PCS


@dataclass(frozen=True)
class DualProviderRow:
    pc: int
    positions: tuple[int, int]
    residents: dict[int, TagePrediction]


async def prepare_rows(agent):
    rows = []
    for pc in SAME_BANK_PCS:
        residents = await fill_useful_set(agent, pc=pc)
        positions = tuple(
            position for position, prediction in residents.items()
            if prediction.meta["providerTableIdx"] == HIGHEST_TABLE
        )
        assert len(positions) == 2 and positions[0] < positions[1], (pc, positions)
        assert {residents[pos].meta["providerWayIdx"] for pos in positions} == {0, 1}
        rows.append(DualProviderRow(pc, positions, residents))
    return tuple(rows)


async def read_pairs(agent, rows):
    """Submit every row before draining: the driver/monitor aligns the replies."""

    transfers = [agent.submit_predict_branches(
        row.pc, tuple(TageBaseBranch(position, 0) for position in row.positions),
    ) for row in rows]
    await agent.drain_predictions()
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(rows), 2))
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in accepted]
    return tuple([await transfer for transfer in transfers])


async def require_neighbors_unchanged(agent, rows):
    for row in rows:
        for position, before in row.residents.items():
            if position in row.positions:
                continue
            after = await agent.predict(row.pc, position, 0)
            # Other output slots are invalid for this scalar request and may
            # refer to selected tags. Compare only the requested branch.
            assert (after.valid, after.taken, after.provider_counter_valid, after.meta) == (
                before.valid, before.taken, before.provider_counter_valid, before.meta,
            ), (hex(row.pc), position, before, after)


def require_pairs(rows, predictions, *, phase):
    for index, (row, prediction) in enumerate(zip(rows, predictions, strict=True)):
        for role, position in enumerate(row.positions):
            before = row.residents[position]
            meta = prediction.metas[role]
            counter = 5 if phase == "resident" else (7 if role else 0)
            if phase == "revisit" and index == 0 and role == 0:
                counter = 1
            state = (hex(row.pc), position, role, phase, prediction)
            assert meta["hasProvider"] == 1, state
            assert (meta["providerTableIdx"], meta["providerWayIdx"]) == (
                HIGHEST_TABLE, before.meta["providerWayIdx"],
            ), state
            assert meta["providerTakenCtr_value"] == counter, state
            assert (prediction.valids[role], prediction.takens[role]) == (1, int(counter >= 4)), state
            assert prediction.provider_counter_valids[role] == 1, state
            old_useful = before.meta["providerUsefulCtr_value"]
            if phase == "resident" or role == 0:
                assert meta["providerUsefulCtr_value"] == old_useful, state
            else:
                # Adjacent training may repeatedly read the same old useful
                # value, unlike serial updates. Require progress for every
                # row, not fictitious per-beat accumulation or equivalence.
                assert old_useful < meta["providerUsefulCtr_value"] <= 3, state


async def check_dual_feedback_mode(agent, coverage, *, adjacent):
    mode = "adjacent" if adjacent else "serial"
    await agent.reset()
    rows = await prepare_rows(agent)
    feedback = tuple(TageBatchTraining(row.pc, tuple(
        TageBranchFeedback(
            position, role, 0, row.residents[position].meta,
            mispredict=int(row.residents[position].taken != role),
        ) for role, position in enumerate(row.positions)
    )) for row in rows) * 8

    stages = []
    for phase in ("resident", "saturated", "revisit"):
        if phase == "saturated":
            # Earlier actual NT + later actual taken is a legal FTQ beat with
            # one real misprediction. Training reads delay both write ports;
            # four distinct keys per port fit the entry-buffer capacity.
            # The useful queue is not claimed to preserve all duplicate beats.
            if adjacent:
                await agent.train_batches(feedback)
            else:
                for transaction in feedback:
                    await agent.train_batch(transaction)
        elif phase == "revisit":
            await agent.train(TageTraining(
                rows[0].pc, rows[0].positions[0], 1, 0, stages[-1][0].metas[0], mispredict=1,
            ))
        predictions = await read_pairs(agent, rows)
        require_pairs(rows, predictions, phase=phase)
        await require_neighbors_unchanged(agent, rows)
        for index, prediction in enumerate(predictions):
            for role in range(2):
                coverage.sample({
                    "mode": mode, "phase": phase, "context": index, "role": role,
                    "way": prediction.metas[role]["providerWayIdx"],
                })
        stages.append(predictions)
    return rows, tuple(stages)
