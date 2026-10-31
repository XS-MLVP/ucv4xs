"""A redirect revokes the in-flight prediction, not the learned record.

The redirect input was bound but never driven: every lookup encoded
``redirect=0``.  This case drives it on a real in-flight window and states the
obligation the module must meet:

* the revoked window publishes a complete flush (no metadata, no valid way);
* the table entry itself survives and still serves the next lookup with its
  original target, position and branch type;
* the redirect is a public input pulse, not an internal write.
"""

from __future__ import annotations

import pytest

from suites.frontend.bpu.abtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.abtb.checker.assertions import assert_miss
from suites.frontend.bpu.abtb.transaction.types import AbtbTraining


async def install(agent):
    cold = await agent.predict(CONDITIONAL.pc, path_hash=0)
    assert_miss(cold)
    await agent.train(AbtbTraining(
        pc=CONDITIONAL.pc,
        target=CONDITIONAL.target,
        taken=1,
        position=CONDITIONAL.position,
        branch_type=CONDITIONAL.branch_type,
        meta=cold.meta,
    ))
    warm = await agent.predict(CONDITIONAL.pc, path_hash=0)
    assert warm.meta["valid"] == 1 and any(entry.valid for entry in warm.entries), (
        "training must publish a resident entry", warm)
    entry = next(entry for entry in warm.entries if entry.valid)
    assert (entry.target, entry.position, entry.branch_type) == (
        CONDITIONAL.target, CONDITIONAL.position, CONDITIONAL.branch_type), warm
    return warm


@pytest.mark.feature("BPU-ABTB-054")
async def test_redirect_flushes_the_inflight_window_and_keeps_the_learned_record(abtb_agent):
    await abtb_agent.reset()
    await install(abtb_agent)

    # A: the accepted lookup that owns the in-flight window.
    # B: the adjacent lookup whose S0 pulse carries the redirect; B's own S0 is
    #    A's S1, which is where the RTL drops the window (`s1_valid` gate).
    first = abtb_agent.submit_predict(CONDITIONAL.pc, path_hash=0)
    second = abtb_agent.submit_predict(
        CONDITIONAL.pc + 0x40, path_hash=1, redirect=True)

    revoked = await first
    assert revoked.meta["valid"] == 0, revoked
    assert all(entry.valid == 0 for entry in revoked.entries), revoked
    assert all(result["valid"] == 0 for result in revoked.micro_tage["result"]), revoked

    await second

    # The redirect must not clear the learned row: the next lookup hits again
    # with the original target/position/type, not a stale or blank entry.
    after = await abtb_agent.predict(CONDITIONAL.pc, path_hash=0)
    entry = next(entry for entry in after.entries if entry.valid)
    assert after.meta["valid"] == 1, after
    assert (entry.target, entry.position, entry.branch_type) == (
        CONDITIONAL.target, CONDITIONAL.position, CONDITIONAL.branch_type), after

    # A redirect pulse that is not followed by a lookup still must not invent
    # or destroy a record when the pipeline is idle.
    idle = abtb_agent.submit_predict(CONDITIONAL.pc, path_hash=0, redirect=True)
    await abtb_agent.drain_predictions()
    await idle
    after_idle = await abtb_agent.predict(CONDITIONAL.pc, path_hash=0)
    entry = next(entry for entry in after_idle.entries if entry.valid)
    assert (entry.target, entry.position) == (CONDITIONAL.target, CONDITIONAL.position), after_idle
