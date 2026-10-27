"""Original capacity peaks, legal transitions, real recovery and serial CBO."""
import pytest

from tests.lsq_wrapper.ldu_joint_owners import LduJointOwners


@pytest.mark.parametrize("seed", (0x7310, 0x7311))
@pytest.mark.parametrize("recovery", ("none", "redirect", "common_reset"))
@pytest.mark.parametrize("response_period", (1, 8))
async def test_source_LDU_joint_capacity_transfer_original_UIDs_three_epochs_and_serial_CBO(lsq, seed, recovery, response_period):
    trace = LduJointOwners(lsq, seed, response_period=response_period)
    old = []
    if recovery != "none":
        await trace.full_first_phase()
        old = list(trace.history)
        if recovery == "redirect":await trace.cancel_first_phase()
        else:
            sequence = await trace.common_reset()
            trace = LduJointOwners(lsq, seed, sequence=sequence, response_period=response_period)
    for _ in range(3):
        _, loads = await trace.full_first_phase()
        await trace.transfer_to_replay_full(loads)
        await trace.fair_drain()
        await trace.serial_cbo()
    trace.assert_reused(old)
    assert trace.sq_head == trace.sq_tail == 396 and trace.lq_head == trace.lq_tail == 708
    assert trace.rob_tail == 1104
    lsq.emit("LDU_joint_three_source_generations_complete", recovery=recovery, response_period=response_period, allocated=len(trace.history),
             completed=sum(s["complete"] for s in trace.history), ROB_tail=trace.rob_tail, SQ_tail=trace.sq_tail, LQ_tail=trace.lq_tail,
             scope="supplemental positive phases only; original eight full-domain mixed outcomes and all STRESS unchecked stay")
