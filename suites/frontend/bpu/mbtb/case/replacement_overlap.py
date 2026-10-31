"""Normal learning and original metadata; all timing stays in agent/drivers."""
from copy import deepcopy

from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback
from suites.frontend.bpu.mbtb.model.replacement_overlap import ReplacementProgram, PC
from suites.frontend.bpu.mbtb.checker.replacement_overlap import ReplacementChecks


def branch(record, *, taken=True, wrong=False):
    return MbtbBranchFeedback(record.target,int(taken),record.position,1,mispredict=int(wrong))


def actual_profile(prediction):
    return tuple((slot,entry.position,entry.target,
                  prediction.meta_entries[slot//5][slot%5]['counter_value'])
                 for slot,entry in enumerate(prediction.entries) if entry.valid)


def semantic_feedback(tx):
    return tx.pc,tuple((b.position,b.target,b.taken,b.branch_type,b.ras_action,b.mispredict) for b in tx.branches)


def actual_feedback(feedback):
    return feedback.pcs[0],tuple((b.position,b.target,int(b.taken),b.kind,b.action,int(b.mispredict))
                               for b in feedback.branches)


async def check_replacement_overlap(agent,coverage,mode):
    program=ReplacementProgram(mode);checks=ReplacementChecks(program,coverage,'mbtb')
    await agent.reset()
    for pc in program.pcs.values():
        first=None
        # Allocate in logical program order, not physical-way order.
        for record in sorted(program.profile(pc,prepared=True),key=lambda r:r.position):
            source=await agent.predict(pc)
            outcomes=(() if first is None else (branch(first,taken=False),))+(branch(record,wrong=True),)
            await agent.train_batch(MbtbBatchTraining(pc,source.meta_entries,outcomes))
            first=record
    touch=await agent.predict(program.touch.pc)
    allocate=await agent.predict(PC)
    frozen=deepcopy((touch.meta_entries,allocate.meta_entries))
    wanted_prepared=tuple(tuple((r.way,r.position,r.target,r.counter) for r in program.profile(pc,prepared=True))
                          for pc in (program.touch.pc,PC))
    checks.sources((actual_profile(touch),actual_profile(allocate)),wanted_prepared)
    first=next(r for r in program.prepared if r.pc==PC and r.position==1)
    allocating=MbtbBatchTraining(PC,allocate.meta_entries,(branch(first,taken=False),branch(program.new,wrong=True)))
    transactions=(allocating,) if program.lookup_only else (
        MbtbBatchTraining(program.touch.pc,touch.meta_entries,(branch(program.touch,taken=program.taken,wrong=program.taken),)),
        allocating)
    before=agent.reference.accepted_feedback[-1][0] if agent.reference.accepted_feedback else -1
    await agent.train_burst(transactions)
    accepted=tuple((tick,fb) for tick,fb in agent.reference.accepted_feedback if tick>before)
    checks.admissions(tuple(tick for tick,_ in accepted),tuple(actual_feedback(fb) for _,fb in accepted),
                      tuple(semantic_feedback(tx) for tx in transactions))
    for pc in program.pcs.values():checks.profile(pc,actual_profile(await agent.predict(pc)))
    checks.immutable(frozen,(touch.meta_entries,allocate.meta_entries))
    agent.reference.raise_failure()
