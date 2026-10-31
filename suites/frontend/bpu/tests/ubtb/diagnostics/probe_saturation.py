"""Diagnostic only: saturated confirmation under forwarded training."""
from suites.frontend.bpu.ubtb.case.definitions import DIRECT
from suites.frontend.bpu.ubtb.checker.assertions import assert_hit
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining


async def test_shape_taken_taken_taken(ubtb_agent):
    await ubtb_agent.reset()
    taken = BranchTraining(DIRECT.pc, DIRECT.target, 1,
                           DIRECT.position, DIRECT.branch_type)
    await ubtb_agent.train_contiguous((taken, taken, taken))
    await assert_hit(ubtb_agent, DIRECT)
