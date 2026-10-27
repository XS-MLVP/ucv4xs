"""Joint pools/fair positive conditions supplement, never replace full random."""
import pytest

from .joint_owners import JointOwners


@pytest.mark.parametrize("seed", (0x7210, 0x7211))
@pytest.mark.parametrize("recovery", ("none", "redirect", "common_reset"))
async def test_simultaneous_all_real_pools_stop_admission_fair_originals_and_full_rob_wraps(lsq, seed, recovery):
    trace = JointOwners(lsq, seed)
    if recovery != "none":
        await trace.full()
        old = list(trace.history)
        if recovery == "redirect":
            await trace.cancel_full()
        else:
            sequence = await trace.common_reset()
            trace = JointOwners(lsq, seed, sequence=sequence)
    else:
        old = []
    for _ in range(3):
        await trace.full()
        await trace.fair_drain()
    trace.assert_reused(old)
    assert trace.rob_tail >= 3*248 and trace.sq_tail == 384 and trace.lq_tail == 360
    lsq.emit("joint_three_complete_generations", allocated=len(trace.history), completed=sum(s["complete"] for s in trace.history),
             recovered_old_same_physical_slot_witnesses=len(old), capacity_rounds=3, absolute_rob_tail=trace.rob_tail,
             whole_STRESS_checked=False, boundary="directed clean disjoint conditions do not replace full-domain random FAILs")
