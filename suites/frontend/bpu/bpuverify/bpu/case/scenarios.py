"""Reusable integrated-BPU predictor states built through public transactions."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.transaction.types import BpuTransaction
from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.assertions import mbtb_meta_for_position
from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.checker.assertions import sc_meta_for_position
from bpuverify.bpu.checker.assertions import tage_meta_for_position
from bpuverify.bpu.case.definitions import EARLIER_TARGET
from bpuverify.bpu.case.definitions import LATER_POSITION
from bpuverify.bpu.case.definitions import LATER_TARGET
from bpuverify.bpu.case.definitions import PC
from bpuverify.bpu.case.definitions import POSITION
from bpuverify.bpu.case.definitions import REDIRECT_PC
from bpuverify.bpu.case.definitions import SC_SAME_WAY_POSITIONS


async def revisit_via_history_path(agent, pc: int, via_pc: int, redirect_meta):
    """Query one PC after a real taken redirect through another PC.

    The intermediate prediction contributes a different path hash; both
    predictions and their S3 metadata are paired by the agent's monitors.
    """

    via = await revisit_from_redirect(agent, via_pc, redirect_meta)
    return await revisit_from_redirect(agent, pc, via.meta.redirect)


@dataclass(frozen=True, slots=True)
class HistoryTageProviders:
    prepared: TwoTageProviders
    anchor: BpuTransaction
    alternate_cold: BpuTransaction
    first: BpuTransaction
    second: BpuTransaction
    via_pc: int


async def prepare_history_tage_providers(agent) -> HistoryTageProviders:
    """Allocate two same-PC TAGE provider cells under real redirect histories."""

    prepared = await prepare_two_tage_providers(agent)
    anchor = prepared.both_providers
    via_pc = REDIRECT_PC + 0x10
    alternate_cold = await revisit_via_history_path(
        agent, PC, via_pc, anchor.meta.redirect
    )
    assert alternate_cold.meta.resolve["phr"] != anchor.meta.resolve["phr"]
    assert tage_meta_for_position(alternate_cold, POSITION)["hasProvider"] == 0
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
        PC, alternate_cold.meta.resolve,
        (BpuBranchFeedback(
            POSITION, EARLIER_TARGET, 1, taken=1, mispredict=1,
        ),),
    ))
    first = await revisit_from_redirect(agent, PC, prepared.cold.meta.redirect)
    second = await revisit_via_history_path(
        agent, PC, via_pc, anchor.meta.redirect
    )
    assert tage_meta_for_position(first, POSITION)["providerTakenCtr_value"] == 2
    assert tage_meta_for_position(second, POSITION)["providerTakenCtr_value"] == 4
    return HistoryTageProviders(
        prepared, anchor, alternate_cold, first, second, via_pc
    )


@dataclass(frozen=True, slots=True)
class TwoTageProviders:
    cold: BpuTransaction
    first_resident: BpuTransaction
    two_mbtb_residents: BpuTransaction
    single_provider: BpuTransaction
    earlier_negative: BpuTransaction
    both_providers: BpuTransaction


async def prepare_two_tage_providers(
    agent, *, positions: tuple[int, int] = (POSITION, LATER_POSITION)
) -> TwoTageProviders:
    """Make two different provider cells for conditional slots 0/2.

    A stable redirect context pairs training and readback history. Tagged
    SRAM training uses the agent's bounded prediction-read pause.
    """

    earlier_position, later_position = positions
    assert 0 <= earlier_position < later_position < 16
    await agent.reset(PC)
    initial = await agent.next_transaction(start_pc=PC)
    await agent.configure_predictors(
        ubtb=False, abtb=False, tage=True, sc=False,
        ittage=False, ras=False, settle=True,
    )
    cold = await revisit_from_redirect(agent, PC, initial.meta.redirect)
    assert cold.prediction.taken == 0

    await agent.train(
        BpuTraining(
            PC, earlier_position, EARLIER_TARGET, cold.meta.resolve,
            branch_type=1,
        )
    )
    first = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    assert mbtb_counter_for_position(first, earlier_position) == 2

    await agent.train_batch(BpuBatchTraining(
        PC, first.meta.resolve,
        (
            BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
            None,
            BpuBranchFeedback(
                later_position, LATER_TARGET, 1, taken=1, mispredict=1,
            ),
        ),
    ))
    residents = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    assert (
        mbtb_counter_for_position(residents, earlier_position),
        mbtb_counter_for_position(residents, later_position),
    ) == (1, 2)
    assert tage_meta_for_position(residents, earlier_position)["hasProvider"] == 0
    assert tage_meta_for_position(residents, later_position)["hasProvider"] == 0

    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
        PC, residents.meta.resolve,
        (BpuBranchFeedback(
            earlier_position, EARLIER_TARGET, 1, taken=1, mispredict=1,
        ),),
    ))
    single = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    assert mbtb_counter_for_position(single, earlier_position) == 2
    assert tage_meta_for_position(single, earlier_position)["providerTakenCtr_value"] == 4

    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
        PC, single.meta.resolve,
        (BpuBranchFeedback(
            earlier_position, EARLIER_TARGET, 1, taken=0, mispredict=1,
        ),),
    ))
    negative = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    assert mbtb_counter_for_position(negative, earlier_position) == 1
    assert tage_meta_for_position(negative, earlier_position)["providerTakenCtr_value"] == 3

    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
        PC, negative.meta.resolve,
        (
            BpuBranchFeedback(earlier_position, EARLIER_TARGET, 1, taken=0),
            None,
            BpuBranchFeedback(
                later_position, LATER_TARGET, 1, taken=0, mispredict=1,
            ),
        ),
    ))
    both = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    assert (
        mbtb_counter_for_position(both, earlier_position),
        mbtb_counter_for_position(both, later_position),
    ) == (0, 1)
    earlier = tage_meta_for_position(both, earlier_position)
    later = tage_meta_for_position(both, later_position)
    assert earlier["hasProvider"] == later["hasProvider"] == 1
    assert (
        earlier["providerTableIdx"], earlier["providerWayIdx"]
    ) != (
        later["providerTableIdx"], later["providerWayIdx"]
    )
    assert (earlier["providerTakenCtr_value"], later["providerTakenCtr_value"]) == (2, 3)

    return TwoTageProviders(cold, first, residents, single, negative, both)


@dataclass(frozen=True, slots=True)
class SameWayScProviders:
    cold: BpuTransaction
    qualified: BpuTransaction


async def prepare_same_way_sc_providers(agent) -> SameWayScProviders:
    """Build two SC-same-way positions with equal, distinct TAGE providers."""

    prepared = await prepare_two_tage_providers(
        agent, positions=SC_SAME_WAY_POSITIONS
    )
    later_position = SC_SAME_WAY_POSITIONS[1]
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
        PC, prepared.both_providers.meta.resolve,
        (None, None, BpuBranchFeedback(
            later_position, LATER_TARGET, 1, taken=0,
        )),
    ))
    equalized = await revisit_from_redirect(
        agent, PC, prepared.cold.meta.redirect
    )
    assert tuple(
        tage_meta_for_position(equalized, position)["providerTakenCtr_value"]
        for position in SC_SAME_WAY_POSITIONS
    ) == (2, 2)

    await agent.configure_predictors(sc=True, settle=True)
    qualified = await revisit_from_redirect(
        agent, PC, prepared.cold.meta.redirect
    )
    sc = qualified.meta.resolve["sc"]
    indices = tuple(
        mbtb_meta_for_position(qualified, position)[0]
        for position in SC_SAME_WAY_POSITIONS
    )
    assert sc["scBiasLowerBits"][indices[0]] == sc["scBiasLowerBits"][indices[1]]
    assert tuple(
        sc_meta_for_position(qualified, position)
        for position in SC_SAME_WAY_POSITIONS
    ) == (
        {"tagePredValid": 1, "tageCtr": 2, "scPred": 1,
         "useScPred": 0, "sumAboveThres": 0},
        {"tagePredValid": 1, "tageCtr": 2, "scPred": 1,
         "useScPred": 0, "sumAboveThres": 0},
    )
    return SameWayScProviders(prepared.cold, qualified)


async def train_sc_feedback_with_tage_held(
    agent, transaction: BpuTransaction,
    branches: tuple[BpuBranchFeedback | None, ...], *, repetitions: int
) -> None:
    """Replay qualified SC feedback without changing TAGE provider cells."""

    await agent.configure_predictors(tage=False, settle=True)
    await agent.train_batch_with_prediction_pause(
        BpuBatchTraining(PC, transaction.meta.resolve, branches),
        repetitions=repetitions,
    )
    await agent.configure_predictors(tage=True, settle=True)
