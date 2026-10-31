"""Two adjacent training cycles exercise MicroBTB's t0/t1 bypass."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining
from suites.frontend.bpu.ubtb.coverage.catalog import ubtb_bypass_recovery_coverage_model
from suites.frontend.bpu.ubtb.coverage.catalog import write_ubtb_bypass_recovery_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ubtb.checker.assertions import assert_hit
from suites.frontend.bpu.ubtb.checker.assertions import assert_miss
from suites.frontend.bpu.ubtb.case.definitions import BranchVector
from suites.frontend.bpu.ubtb.case.definitions import CONDITIONAL
from suites.frontend.bpu.ubtb.case.definitions import DIRECT


@pytest.mark.feature("BPU-UBTB-011")
async def test_contiguous_allocation_and_aging_are_not_lost(ubtb_agent):
    await ubtb_agent.reset()
    taken = BranchTraining(
        pc=DIRECT.pc,
        target=DIRECT.target,
        taken=1,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
    not_taken = BranchTraining(
        pc=DIRECT.pc,
        target=DIRECT.target,
        taken=0,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )

    transfers = await ubtb_agent.train_contiguous((taken, not_taken))
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted[1] - accepted[0] == 2, accepted

    # The adjacent not-taken request must see the allocation in t1 through
    # the bypass and decrease its useful counter from 3 to 2.
    await assert_hit(ubtb_agent, DIRECT)
    await ubtb_agent.train(not_taken)
    await assert_hit(ubtb_agent, DIRECT)
    await ubtb_agent.train(not_taken)
    await assert_miss(ubtb_agent, DIRECT.pc)


@pytest.mark.feature("BPU-UBTB-012")
async def test_contiguous_aging_to_zero_then_taken_reinitializes(ubtb_agent):
    await ubtb_agent.reset()
    taken = BranchTraining(
        pc=DIRECT.pc,
        target=DIRECT.target,
        taken=1,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
    not_taken = BranchTraining(
        pc=DIRECT.pc,
        target=DIRECT.target,
        taken=0,
        position=DIRECT.position,
        branch_type=DIRECT.branch_type,
    )
    replacement = BranchVector(
        DIRECT.pc, DIRECT.target + 0x100, DIRECT.position, DIRECT.branch_type
    )
    changed_taken = BranchTraining(
        pc=replacement.pc,
        target=replacement.target,
        taken=1,
        position=replacement.position,
        branch_type=replacement.branch_type,
    )

    transfers = await ubtb_agent.train_contiguous(
        (taken, not_taken, not_taken, not_taken, changed_taken)
    )
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 10, 2)), accepted
    await assert_hit(ubtb_agent, replacement)

    # A changed target at useful=0 must reinitialize the entry and payload.
    # Three later not-taken updates should be needed to invalidate the entry.
    for _ in range(2):
        await ubtb_agent.train(not_taken)
        await assert_hit(ubtb_agent, replacement)
    await ubtb_agent.train(not_taken)
    await assert_miss(ubtb_agent, DIRECT.pc)


@pytest.mark.feature("BPU-UBTB-010")
async def test_contiguous_saturated_confirmation_holds_the_upper_bound(ubtb_agent):
    """Three adjacent taken confirmations saturate at the strong bound.

    A forwarded hit that already reads the maximum reliability must keep it:
    the counter neither wraps to zero nor skips a decrement step. The entry
    must still be a taken hit, and it must then take three real not-taken
    reports to become invalid, not two and not four.
    """

    await ubtb_agent.reset()
    taken = BranchTraining(DIRECT.pc, DIRECT.target, 1,
                           DIRECT.position, DIRECT.branch_type)
    not_taken = BranchTraining(DIRECT.pc, DIRECT.target, 0,
                               DIRECT.position, DIRECT.branch_type)
    await ubtb_agent.train_contiguous((taken, taken, taken))
    await assert_hit(ubtb_agent, DIRECT)
    for _ in range(2):
        await ubtb_agent.train(not_taken)
        await assert_hit(ubtb_agent, DIRECT)
    await ubtb_agent.train(not_taken)
    await assert_miss(ubtb_agent, DIRECT.pc)


@pytest.mark.feature("BPU-UBTB-011")
async def test_fallthrough_does_not_revive_a_dead_entry_with_its_target(ubtb_agent):
    """The revived entry must not install the not-taken branch's target.

    After contiguous taken + three not-taken reports the entry is dead. A
    fourth contiguous not-taken report whose target differs must not turn that
    target into a taken prediction. The harness keeps this an ordinary FAIL if
    the RTL forwards a stale hit qualifier; it is not rewritten as XFAIL.
    """

    await ubtb_agent.reset()
    taken = BranchTraining(CONDITIONAL.pc, CONDITIONAL.target, 1,
                           CONDITIONAL.position, CONDITIONAL.branch_type)
    other_target = CONDITIONAL.target + 0x200
    fallthrough = BranchTraining(CONDITIONAL.pc, other_target, 0,
                                 CONDITIONAL.position, CONDITIONAL.branch_type)
    await ubtb_agent.train_contiguous((taken, fallthrough, fallthrough,
                                       fallthrough, fallthrough))
    actual = await ubtb_agent.predict(CONDITIONAL.pc)
    assert actual.valid == 0


@pytest.mark.feature('BPU-UBTB-010')
@pytest.mark.feature('BPU-UBTB-011')
@pytest.mark.feature('BPU-UBTB-012')
async def test_contiguous_recovery_and_reinitialization_forward_to_next_feedback(ubtb_agent):
    coverage = ubtb_bypass_recovery_coverage_model()
    taken = BranchTraining(DIRECT.pc, DIRECT.target, 1, DIRECT.position, DIRECT.branch_type)
    not_taken = BranchTraining(DIRECT.pc, DIRECT.target, 0, DIRECT.position, DIRECT.branch_type)
    changed = BranchVector(DIRECT.pc, DIRECT.target + 0x200, DIRECT.position, DIRECT.branch_type)
    changed_taken = BranchTraining(changed.pc, changed.target, 1, changed.position, changed.branch_type)
    for transactions, vector, payload_phase, counter_phase in (
        ((taken, not_taken, taken, taken), DIRECT,
         'recovery_forwarded', 'recovery_counter_three'),
        ((taken, not_taken, not_taken, not_taken, changed_taken, changed_taken), changed,
         'reinitialized_payload_forwarded', 'reinitialized_counter_three'),
    ):
        await ubtb_agent.reset()
        transfers = await ubtb_agent.train_contiguous(transactions)
        ticks = [transfer.accepted_event.tick for transfer in transfers]
        assert ticks == list(range(ticks[0], ticks[0] + 2 * len(transactions), 2)), ticks
        await assert_hit(ubtb_agent, vector)
        coverage.sample({'phase': payload_phase})
        # Infer useful=3 architecturally; internal counter reads cannot stand
        # in for checking that the forwarded value actually reached entries.
        for _ in range(2):
            await ubtb_agent.train(not_taken)
            await assert_hit(ubtb_agent, vector)
        await ubtb_agent.train(not_taken)
        await assert_miss(ubtb_agent, vector.pc)
        coverage.sample({'phase': counter_phase})
    coverage.assert_coverage(100.0)
    write_ubtb_bypass_recovery_coverage(coverage, REPO_ROOT)
