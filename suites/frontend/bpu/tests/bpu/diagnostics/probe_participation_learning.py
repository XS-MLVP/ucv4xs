"""Explicit-only probe: what does ITTAGE do with late feedback for an unserved original?"""
import json

from bpuverify.bpu.checker.assertions import revisit_from_redirect
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback

PC = 0x40001800
POSITION = 4
TARGET = 0x40002800


async def test_probe_late_unserved_feedback(bpu_agent, request):
    await bpu_agent.reset(PC)
    await bpu_agent.configure_predictors(
        ubtb=False, abtb=False, mbtb=True, tage=False, sc=False,
        ittage=False, ras=False, settle=True,
    )
    old = await bpu_agent.next_transaction(start_pc=PC)
    old_ittage = dict(old.meta.resolve["ittage"])
    await bpu_agent.configure_predictors(ittage=True, settle=True)
    fresh = await revisit_from_redirect(bpu_agent, PC, old.meta.redirect)
    fresh_ittage = dict(fresh.meta.resolve["ittage"])
    transaction = BpuBatchTraining(
        PC,
        old.meta.resolve,
        (BpuBranchFeedback(POSITION, TARGET, branch_type=3, taken=1, mispredict=1),),
    )
    await bpu_agent.train_batch_with_prediction_pause(transaction)
    after = await revisit_from_redirect(bpu_agent, PC, fresh.meta.redirect)
    evidence = dict(
        old=old_ittage,
        fresh=fresh_ittage,
        after=dict(after.meta.resolve["ittage"]),
        resolve_keys=sorted(after.meta.resolve.keys()),
        after_prediction=dict(target=after.prediction.target, taken=after.prediction.taken,
                             position=after.prediction.position),
    )
    request.node.user_properties.append(
        ("late_unserved_feedback_probe", json.dumps(evidence, ensure_ascii=False))
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
