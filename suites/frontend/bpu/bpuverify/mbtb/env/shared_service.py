"""Create genuine duplicate and neighbor lifetimes through existing drivers."""
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import replace
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.cleanup_overlap_scenario import feedback
from bpuverify.mbtb.case.resident_scenario import snapshot
from bpuverify.mbtb.checker.assertions import assert_miss,assert_vector_hit,matching_way
from bpuverify.mbtb.transaction.types import MbtbBatchTraining,MbtbBranchFeedback


@asynccontextmanager
async def shared_service_program(agent,program):
    await agent.reset()
    first=BranchVector(0x40000020+(program.tag<<11),0x40002340,5,3)
    neighbor=replace(first,pc=first.pc+64,target=first.target+0x1020)
    extra=replace(neighbor,position=6,target=neighbor.target+0x200)
    corrected=replace(first,target=first.target+0x400)
    sources=[];captures=[]
    for pc in (first.pc,neighbor.pc,first.pc,neighbor.pc):
        transfer=agent.submit_predict(pc);sources.append(await transfer)
        captures.append(dict(pc=pc,accepted_tick=transfer.accepted_event.tick,
            completed_tick=transfer.completed_event.tick))
    cold,other_cold,replay,old_neighbor=sources
    for source in sources:assert_miss(source)
    originals=deepcopy(tuple(source.meta_entries for source in sources))
    async with agent.defer_multi_hit_cleanup():
        await agent.train_batch(feedback(first,cold.meta_entries))
        await agent.train_batch(feedback(neighbor,other_cold.meta_entries))
        current=await agent.predict(neighbor.pc)
        await agent.train_batch(feedback(extra,current.meta_entries))
        await agent.train_batch(feedback(corrected,replay.meta_entries))
        before_neighbor=await agent.predict(neighbor.pc)
        assert_vector_hit(before_neighbor,neighbor);assert_vector_hit(before_neighbor,extra)
        assert matching_way(before_neighbor,neighbor)==1 and matching_way(before_neighbor,extra)==0
        # A real correct-taken access makes the old miss nominate the peer.
        # No entry correction occurs, so the already served neighbor retains
        # its own logical owner in the independent model and the DUT.
        if program.shared:
            await agent.train_batch(MbtbBatchTraining(neighbor.pc,deepcopy(before_neighbor.meta_entries),(
                MbtbBranchFeedback(neighbor.target,1,neighbor.position,3,mispredict=0),)))
        duplicate=await agent.predict(first.pc)
        assert [(e.position,e.target) for e in duplicate.entries if e.valid]==[(5,corrected.target),(5,first.target)]
        selected=neighbor if program.shared else extra
        updated=replace(selected,target=selected.target+0x800)
        metadata=old_neighbor.meta_entries if program.shared else before_neighbor.meta_entries
        transaction=feedback(updated,metadata)
        cache=agent.reference.model.entries[0,0]
        expected_key=('branch',(neighbor.pc>>5)&63,(neighbor.pc>>11)&65535,selected.position)
        retained=cache.records.get(expected_key)
        if program.shared:
            assert retained is not None and retained.write.way==1
            assert retained.sequence not in cache.outstanding
        assert not cache.outstanding
        yield dict(first=first,neighbor=neighbor,extra=extra,updated=updated,
            duplicate=duplicate,before_neighbor=before_neighbor,transaction=transaction,
            originals=originals,sources=tuple(sources),source_captures=captures,
            retained_before=dict(owner=retained.write.way if retained is not None else 0,
                rank=retained.rank if retained is not None else None,record_exists=retained is not None,pending=False),
            expected_key=expected_key,capacity_before=2)
