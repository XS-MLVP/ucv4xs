from __future__ import annotations

from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.transaction.types import BpuTransaction
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.definitions import PREDICTION_LIMIT
from suites.frontend.bpu.bpu.case.definitions import TARGET


async def train_direct_branch(agent, cold: BpuTransaction | None = None):
    if cold is None:
        cold = await agent.next_transaction(start_pc=PC)
    assert cold.prediction.taken == 0
    await agent.train(BpuTraining(PC, POSITION, TARGET, cold.meta.resolve))
    await agent.redirect(BpuRedirect(PC, cold.meta.redirect))
    _, trained = await agent.next_prediction(
        start_pc=PC,
        require_taken=True,
        limit=PREDICTION_LIMIT,
    )
    return cold.meta, trained


def mbtb_meta_for_position(transaction: BpuTransaction, position: int):
    """Pair a resolved branch position with its flattened MainBTB metadata slot."""

    entries = (
        entry
        for bank in transaction.meta.resolve["mbtb_entries"]
        for entry in bank
    )
    matches = [
        (index, entry)
        for index, entry in enumerate(entries)
        if entry["rawHit"] and entry["position"] == position
    ]
    assert len(matches) == 1, (
        f"expected one MainBTB entry at position {position}, "
        f"meta={transaction.meta.resolve['mbtb_entries']!r}"
    )
    return matches[0]


def mbtb_counter_for_position(transaction: BpuTransaction, position: int) -> int:
    return mbtb_meta_for_position(transaction, position)[1]["counter_value"]


def tage_meta_for_position(transaction: BpuTransaction, position: int):
    index, _ = mbtb_meta_for_position(transaction, position)
    entries = transaction.meta.resolve["tage_entries"]
    assert index < len(entries), (
        f"missing TAGE metadata for MainBTB slot {index}, "
        f"meta={entries!r}"
    )
    return entries[index]


def tage_provider_signatures(transaction: BpuTransaction, positions):
    signatures = []
    for position in positions:
        meta = tage_meta_for_position(transaction, position)
        assert meta["hasProvider"] == 1, (position, meta)
        signatures.append((
            meta["providerTableIdx"],
            meta["providerWayIdx"],
            meta["providerTakenCtr_value"],
        ))
    return tuple(signatures)


def sc_meta_for_position(transaction: BpuTransaction, position: int):
    index, _ = mbtb_meta_for_position(transaction, position)
    meta = transaction.meta.resolve["sc"]
    fields = (
        "tagePredValid", "tageCtr", "scPred", "useScPred", "sumAboveThres",
    )
    assert all(index < len(meta[field]) for field in fields), (
        f"missing SC metadata for MainBTB slot {index}, meta={meta!r}"
    )
    return {field: meta[field][index] for field in fields}


def sc_decisions_for_positions(transaction: BpuTransaction, positions):
    """Return (SC direction, SC used, above threshold) for each position."""

    return tuple(
        (
            meta["scPred"], meta["useScPred"], meta["sumAboveThres"],
        )
        for meta in (
            sc_meta_for_position(transaction, position) for position in positions
        )
    )


async def revisit_from_redirect(agent, pc: int, redirect_meta):
    boundary = await agent.redirect(BpuRedirect(pc, redirect_meta))
    return await agent.next_transaction(start_pc=pc, after_tick=boundary)
