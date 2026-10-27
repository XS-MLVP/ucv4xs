"""Default requests must be checked even without testcase-supplied expected."""
import pytest
from dataclasses import replace

from bpuverify.ubtb.case.definitions import CONDITIONAL, DIRECT, INDIRECT
from bpuverify.ubtb.checker.assertions import train_taken
from bpuverify.ubtb.transaction.types import BranchTraining


@pytest.mark.feature('BPU-UBTB-013')
async def test_default_parallel_predictions_use_the_independent_cache(ubtb_agent):
    await ubtb_agent.reset()
    for vector in (CONDITIONAL, DIRECT, INDIRECT):
        await train_taken(ubtb_agent, vector)
    before = ubtb_agent.reference.board.status.checked
    vectors = (DIRECT, CONDITIONAL, INDIRECT, DIRECT)
    transfers = [ubtb_agent.submit_predict(vector.pc) for vector in vectors]
    await ubtb_agent.drain_predictions()
    assert all(callable(call.expected) for call in transfers)
    actuals = [await call for call in transfers]  # Already completed by drain.
    assert [actual.target for actual in actuals] == [vector.target for vector in vectors]
    status = ubtb_agent.reference.board.status
    assert status.failed == 0 and status.checked >= before + len(transfers)
    assert status.passed == status.checked


@pytest.mark.feature('BPU-UBTB-011')
@pytest.mark.parametrize('consecutive', [False, True], ids=['separated', 'consecutive'])
async def test_contiguous_fallthrough_does_not_reallocate_a_dead_entry(ubtb_agent, consecutive):
    """Taken allocation → three confidence losses → another fall-through.

    A forwarded hit is not a semantic reason to turn not-taken feedback into
    a taken hit. Keep a normal failure for a contract/RTL disagreement, not
    an XFAIL or a reference-state resynchronization to the actual result.
    """
    await ubtb_agent.reset()
    # A conditional branch makes both actual directions architecturally legal.
    taken = BranchTraining(CONDITIONAL.pc, CONDITIONAL.target, 1,
                           CONDITIONAL.position, CONDITIONAL.branch_type)
    fallthrough = replace(taken, taken=0)
    feedback = (taken, fallthrough, fallthrough, fallthrough, fallthrough)
    if consecutive:
        await ubtb_agent.train_contiguous(feedback)
    else:
        for transaction in feedback:
            await ubtb_agent.train(transaction)
    actual = await ubtb_agent.predict(CONDITIONAL.pc)
    assert actual.valid == 0
