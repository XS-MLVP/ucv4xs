"""Repeated genuine duplicates must reclaim every way pair, not just the first.

A stale but genuine snapshot can allocate the same branch twice.  The cleanup
must leave exactly one copy, and it must be the newly written copy: the older
duplicate is the one that is invalidated.  The victim rotates, so the same set
produces the (0,2), (2,3), (1,3) and (0,3) pairs in turn.  The (2,3) pair is the
one that drives the upper half of the multi-hit priority encoder; covering only
the first duplicate never reaches it.
"""

from __future__ import annotations

import json

import pytest

from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.abtb.case.definitions import DIRECT
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining
from suites.frontend.bpu.runtime.artifacts import write_output
from suites.frontend.bpu.runtime.paths import REPO_ROOT

ROUNDS = 6


def copies(prediction, vector):
    """Ways that hold the trained branch, by position and type, not by tag."""
    return tuple(way for way, entry in enumerate(prediction.entries)
                 if entry.valid
                 and entry.position == vector.position
                 and entry.branch_type == vector.branch_type)


def training_for(vector, meta):
    return AbtbTraining(
        pc=vector.pc,
        target=vector.target,
        taken=1,
        position=vector.position,
        branch_type=vector.branch_type,
        meta=meta,
    )


@pytest.mark.feature("BPU-ABTB-028")
@pytest.mark.parametrize(("vector", "bank"), ((CONDITIONAL, 0), (DIRECT, 2)),
                         ids=("conditional-bank0", "direct-bank2"))
async def test_repeated_stale_snapshot_reclaims_each_duplicate_pair(abtb_agent, vector, bank):
    await abtb_agent.reset()
    cold = await abtb_agent.predict(vector.pc, path_hash=bank)
    assert_miss(cold)
    assert cold.meta["bankMask"] == 1 << bank
    stale = training_for(vector, cold.meta)

    await abtb_agent.train(stale)
    first = await abtb_agent.predict(vector.pc, path_hash=bank)
    first_copies = copies(first, vector)
    assert len(first_copies) == 1, (vector, first)

    observed = []
    for round_index in range(ROUNDS):
        # The same real cold snapshot is reused: its hit bits are clear, so the
        # DUT treats this as a genuine miss and allocates the current victim.
        await abtb_agent.train(stale)
        duplicate = await abtb_agent.predict(vector.pc, path_hash=bank)
        ways = copies(duplicate, vector)
        assert 1 <= len(ways) <= 2, (round_index, ways, duplicate)
        if len(ways) == 2:
            # Both copies are complete, so this is a real duplicate request.
            for way in ways:
                entry = duplicate.entries[way]
                assert (entry.taken, entry.target) == (1, vector.target), (round_index, way, entry)
        observed.append(dict(round=round_index, before=list(ways)))

        # Reads outrank buffered writes in the single-port bank; the agent
        # supplies a quiet window instead of exposing a driver or clock edge.
        await abtb_agent.drain_bank_writes()
        cleaned = await abtb_agent.predict(vector.pc, path_hash=bank)
        remaining = copies(cleaned, vector)
        assert len(remaining) == 1, (round_index, ways, remaining, cleaned)
        retained = cleaned.entries[remaining[0]]
        assert (retained.taken, retained.target) == (1, vector.target), (round_index, retained)
        observed[-1]["after"] = list(remaining)
        if len(ways) == 2:
            # The stale re-allocation is the newest write: cleanup removes the
            # older copy and keeps the newly allocated one.
            assert remaining[0] == max(ways), (round_index, ways, remaining)

    pairs = {tuple(row["before"]) for row in observed if len(row["before"]) == 2}
    # The victim rotation produces the upper-half pair, which the single
    # duplicate of the existing case never reaches.
    assert (2, 3) in pairs, observed
    assert all(len(row["after"]) == 1 for row in observed), observed
    write_output(
        REPO_ROOT / "results" / "abtb" / f"multi-hit-pairs-{vector.position}.json",
        json.dumps(dict(vector=dict(pc=hex(vector.pc), position=vector.position,
                                    branch_type=vector.branch_type, target=hex(vector.target)),
                        bank=bank, rounds=observed), indent=2, sort_keys=True) + "\n")
