"""Diagnostic only: per-shape contiguous analysis; failures are expected."""
from bpuverify.ubtb.case.definitions import DIRECT
from bpuverify.ubtb.transaction.types import BranchTraining


def seq(*directions):
    return tuple(
        BranchTraining(DIRECT.pc, DIRECT.target, taken, DIRECT.position, DIRECT.branch_type)
        for taken in directions
    )


async def test_shape_taken_taken(ubtb_agent):
    await ubtb_agent.reset()
    await ubtb_agent.train_contiguous(seq(1, 1))
    await ubtb_agent.predict(DIRECT.pc)


async def test_shape_taken_nt_taken_taken(ubtb_agent):
    await ubtb_agent.reset()
    await ubtb_agent.train_contiguous(seq(1, 0, 1, 1))
    await ubtb_agent.predict(DIRECT.pc)


async def test_shape_taken_nt_x4(ubtb_agent):
    await ubtb_agent.reset()
    await ubtb_agent.train_contiguous(seq(1, 0, 0, 0, 0))
    await ubtb_agent.predict(DIRECT.pc)


async def test_shape_taken_nt_x3(ubtb_agent):
    await ubtb_agent.reset()
    await ubtb_agent.train_contiguous(seq(1, 0, 0, 0))
    await ubtb_agent.predict(DIRECT.pc)
