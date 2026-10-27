"""Normal StoreUnit CBO packages, original full-domain seeds and joint loads.

These are new tests, not rewrites of frozen interface histories. Every cycle
still uses strict all-output WrapperEnv; no probe/skip/known-issue filtering.
"""
import pytest

from .normal_mixed_owners import NormalJointOwners, NormalMixedOwners


@pytest.mark.parametrize("seed", range(0x7100,0x7108))
async def test_normal_cbo_full_domain_original_seed_all_kinds_and_fair_obligations(lsq,seed):
    await NormalMixedOwners(lsq,seed).run()


@pytest.mark.parametrize("seed",(0x7210,0x7211))
@pytest.mark.parametrize("recovery",("none","redirect","common_reset"))
async def test_normal_cbo_joint_all_pools_actual_fair_three_generations_and_recovery(lsq,seed,recovery):
    trace=NormalJointOwners(lsq,seed)
    if recovery!="none":
        await trace.full()
        old=list(trace.history)
        if recovery=="redirect":
            await trace.cancel_full()
        else:
            sequence=await trace.common_reset()
            trace=NormalJointOwners(lsq,seed,sequence=sequence)
    else:
        old=[]
    for _ in range(3):
        await trace.full()
        await trace.fair_drain()
    trace.assert_reused(old)
    assert trace.rob_tail>=744 and trace.sq_tail==384 and trace.lq_tail==360
    lsq.emit("normal_CBO_three_generations_actual_completion",capacity_rounds=3,
             completed=sum(s["complete"] for s in trace.history),cancelled_or_reset_same_slot=len(old),
             scope="real QB/fullmask/wline CBO; directed clean joint condition, not whole-STRESS acceptance")
