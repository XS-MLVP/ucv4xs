"""Diagnostic only: saturated confirmation under forwarded training."""
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.checker.assertions import assert_hit
from bpuverify.ubtb.transaction.types import BranchTraining


async def test_shape_taken_taken_taken(ubtb_agent):
    await ubtb_agent.reset()
    taken = BranchTraining(DIRECT.pc, DIRECT.target, 1,
                           DIRECT.position, DIRECT.branch_type)
    await ubtb_agent.train_contiguous((taken, taken, taken))
    await assert_hit(ubtb_agent, DIRECT)
