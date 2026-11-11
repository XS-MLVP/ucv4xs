
from dataclasses import replace
import hashlib

from suites.memblock.lsq.testbenches.store_queue.model.sq_scalar_reservation import DOMAIN
from suites.memblock.lsq.testbenches.store_queue.model.sq_scalar_reservation import save
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.model.vsq_recovery import PublicWindow
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.recovery_owners import RecoveryOwners


class ObservedPool(RecoveryOwners):
    def __init__(self,env):
        super().__init__(env)
        self.observation=None

    async def cycle(self,**fields):
        await super().cycle(**fields)
        if self.observation is not None:
            self.observation.observe_wrapper(self.env.response,self.env.last_tick)


def owner(position,program,generation):
    return StoreOwner(position,RobPtr.encode(program),0xB00000+(generation*512+position)*64,
                      0xF000000+(generation*512+position)*64,
                      value=0x1234567800000000|generation<<20|position*0x101)


async def test_interface_128_scalar_pool_shared_recovery_exact_new_Stores_and_original_Loads(lsq,tmp_path):
    trace,profiles,stream,program=ObservedPool(lsq),[],hashlib.sha256(),10
    for phase,base in enumerate((0,128)):
        assert trace.sq_head==base
        branch=RobPtr.encode(program-1)
        trace.base=replace(trace.base,pending=branch,pending_next=branch,sbuffer_ready=(False,False))
        lsq.emit("scalar_reservation_interface_domain",domain=DOMAIN,physical_base=base,
                 normal_full_core_producer_proven=False)
        old=[owner(base+index,program+index,phase) for index in range(128)]
        for first in range(0,128,2):
            await trace.dispatch(stores=old[first:first+2])
            if first<64:
                await trace.write_all(item.position for item in old[first:first+2])
        old_load=cached_load(phase,program+128,base+128,old[-1].vaddr,old[-1].paddr)
        await trace.dispatch(loads=[old_load]);await trace.idle(5)
        old_states=[trace.stores[item.position] for item in old]
        old_uids=[state["uid"] for state in old_states]
        assert lsq.response.sq_full==0 and trace.sq_head==base
        assert all(state["s2_done"] and state["data_sent"] for state in old_states[:64])
        assert all(not state["address_parts"] and not state["data_sent"] for state in old_states[64:])
        assert all(not state["consumed"] and not state["completed"] for state in old_states)
        assert not trace.active_loads[old_load.execution.uop.lq]["sent"]
        trace.observation=PublicWindow("lsq_wrapper")
        assert await trace.cancel(branch,flush_self=False)==(QueuePtr.encode(phase),base%256)
        recovery=trace.observation.finish(base,phase);trace.observation=None
        assert lsq.response.sq_full==0
        new=[owner(base+index,program+index,phase+8) for index in range(128)]
        for first in range(0,128,2):
            await trace.dispatch(stores=new[first:first+2])
        new_load=cached_load(phase,program+128,base+128,new[-1].vaddr,new[-1].paddr)
        await trace.dispatch(loads=[new_load])
        await trace.write_all(item.position for item in new[:64])
        assert trace.sq_head==base and all(not trace.stores[item.position]["consumed"] for item in new)
        for retired in range(8,65,8):
            boundary=RobPtr.encode(program+retired)
            trace.base=replace(trace.base,pending=boundary,pending_next=boundary,sbuffer_ready=(True,True))
            await trace.cycle()
        for _ in range(100):
            await trace.cycle()
            if trace.sq_head==base+64:
                break
        assert trace.sq_head==base+64 and all(trace.stores[item.position]["completed"] for item in new[:64])
        trace.base=replace(trace.base,sbuffer_ready=(False,False))
        await trace.write_all(item.position for item in new[64:])
        assert all(not trace.stores[item.position]["consumed"] for item in new[64:])
        response=await trace.forward(new_load,phase)
        assert response.valid==1 and not any((response.forward_invalid,response.match_invalid,
            response.addr_invalid,response.data_invalid)),("scalar-pool-original-Load-bytes",response)
        assert response.forward_mask==0xFF,("scalar-pool-original-Load-bytes",response)
        for byte in range(8):
            assert response.forward_data>>(8*byte)&255==new[-1].value>>(8*byte)&255,("scalar-pool-original-Load-bytes",byte,response)
        await trace.execute([new_load]);await trace.idle(8)
        assert trace.active_loads[new_load.execution.uop.lq]["completed"]
        for retired in range(72,129,8):
            boundary=RobPtr.encode(program+retired)
            trace.base=replace(trace.base,pending=boundary,pending_next=boundary,sbuffer_ready=(True,True))
            await trace.cycle()
        await trace.finish(pending=RobPtr.encode(program+128))
        reused=[[state["uid"],trace.stores[item.position]["uid"],item.position] for state,item in zip(old_states,new)]
        assert all(state["owner"].position==item.position and state["uid"]<trace.stores[item.position]["uid"]
                   and not state["completed"] and not state["consumed"] and trace.stores[item.position]["completed"] for state,item in zip(old_states,new))
        new_uids=[trace.stores[item.position]["uid"] for item in new]
        item=dict(phase=phase,physical_base=base,reserved_scalar_uops=128,flows_per_uop=1,
            old_executed_uids=old_uids[:64],old_unexecuted_uids=old_uids[64:],actual_recovered_tail=base%256,
            recovery=recovery,reuse_old_new_absolute_position=reused,new_completed_uids=new_uids,
            actual_Sbuffer_fragments=128,actual_physical_tail=trace.sq_head,old_consumed_fragments=0,
            older_nonmemory_branch_flushAfter=True,max_dispatch_stores_per_cycle=2,
            original_Load_PA_bytes_checked=True,new_Load_S3_completed=True,cancelled_Load_uids=1,normal_Load_uids=1)
        profiles.append(item);add_digest(stream,item)
        for store in new:
            state=trace.stores[store.position]
            add_digest(stream,["actual_original_bytes_fire_then_dequeue",state["uid"],store.position,state["last_fire"]])
        program+=129
    assert trace.sq_head==len(trace.stores)==len(trace.fragments_fired)==256
    assert trace.load_released==2 and len(trace.cancelled)==2
    assert len([state for state in trace.abort_history if "owner" in state])==256
    lsq.prove("LSQ-ALLOC.sq_capacity","LSQ-RECOVER.all","LSQ-RECOVER.reuse","LSQ-FORWARD.sqid")
    save(tmp_path/"sq-scalar-reservation-witness.json","lsq_wrapper",profiles,stream,normal_store_uids=256,
         cancelled_store_uids=256,exact_absolute_position_reuses=256,actual_Sbuffer_fragments=256,
         resets_between_profiles=0,normal_Load_uids=2,cancelled_Load_uids=2)
