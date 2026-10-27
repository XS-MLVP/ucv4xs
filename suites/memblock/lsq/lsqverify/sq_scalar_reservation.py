"""128scalar LSQ-interface reservation; full-core IQ reachability is NOT claimed."""
import hashlib
import json

from lsqverify.store_payload import add_digest
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq_recovery import PublicWindow

DOMAIN = "UNIT_INTERFACE_LSQ_CAPACITY"


def save(path, dut, profiles, stream, **totals):
    path.write_text(json.dumps(dict(format="lsq-sq-scalar-reservation-witness-v1",dut=dut,domain=DOMAIN,
        normal_full_core_producer_proven=False,profiles=profiles,public_lifetime_SHA256=stream.hexdigest(),
        **totals),indent=2)+"\n")


async def store_trace(env,actor,path):
    profiles,stream=[],hashlib.sha256()
    for phase,base in enumerate((0,128)):
        assert actor.head==actor.tail==base and not actor.live
        actor.emit("scalar_reservation_interface_domain",domain=DOMAIN,physical_base=base,
                   normal_full_core_producer_proven=False)
        old=[actor.add(lane=index%2) for index in range(128)]
        old_uids=[item.flows[0] for item in old]
        branch=RobPtr.encode(old[0].rob_order-1,former=bool((old[0].rob_order-1)%2))
        for _ in range(200):
            await actor.step(fair=True,advance_rob=False,sbuffer_ready=(False,False),rob_head=branch)
            if all(item.dispatched for item in old) and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in old_uids[:64]):
                break
        assert all(item.dispatched and not item.retired_by_rob for item in old)
        assert all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in old_uids[:64])
        assert all(not actor.all[uid].address_parts and not actor.all[uid].data_sent for uid in old_uids[64:])
        for _ in range(3):
            await actor.step(fair=True,issue=False,advance_rob=False,sbuffer_ready=(False,False),rob_head=branch)
        # Public sqFull is registered PSQ reserved-flow overflow (>128), NOT
        # the removed VSQ canAccept/full signal. Exactly128 is still0.
        assert env.observed["io_sqFull"]==0 and actor.head==base
        assert all(not actor.parts[uid] and uid not in actor.completed for uid in old_uids)
        observation=PublicWindow("store_queue")
        for tick in range(35):
            await actor.step(fair=True,issue=False,dispatch=False,advance_rob=False,
                rob_head=branch,redirect=Redirect(tick==0,branch,False),sbuffer_ready=(False,False))
            observation.observe(env.observed,env.last_tick)
            if tick>=10 and not env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
                break
        assert tick<34
        recovery=observation.finish(base)
        assert env.observed["io_sqFull"]==0
        for item in old:
            assert not item.retired_by_rob
            actor.active_uops.remove(item.uid)
        for uid in old_uids:
            assert uid not in actor.completed and not actor.parts[uid]
            actor.cancelled.add(uid)
            del actor.live[actor.all[uid].position]
        actor.tail=actor.dispatched_tail=base
        actor.next_rob=old[0].rob_order
        actor.s2=((None,True),)*2
        actor.emit("scalar_pool_branch_cancel",domain=DOMAIN,physical_base=base,cancelled=old_uids,recovery=recovery)
        new=[actor.add(lane=index%2) for index in range(128)]
        new_uids=[item.flows[0] for item in new]
        reused=[[a.flows[0],b.flows[0],b.start] for a,b in zip(old,new)]
        assert all(a.start==b.start and a.end==b.end and b.flows[0]>old_uids[-1] for a,b in zip(old,new))
        await actor.drain()
        assert set(new_uids)<=actor.completed and all(actor.parts[uid]=={0} for uid in new_uids)
        assert all(not actor.parts[uid] and uid not in actor.completed for uid in old_uids)
        assert actor.head==actor.tail==base+128 and not actor.live
        actor.checked(("SQ-INTERFACE.scalar_pool","SQ-REUSE.cancelled"),new_uids)
        item=dict(phase=phase,physical_base=base,reserved_scalar_uops=128,flows_per_uop=1,
            old_executed_uids=old_uids[:64],old_unexecuted_uids=old_uids[64:],
            actual_recovered_tail=base%256,recovery=recovery,reuse_old_new_absolute_position=reused,
            new_completed_uids=new_uids,actual_Sbuffer_fragments=128,actual_physical_tail=actor.head,
            old_consumed_fragments=0,older_nonmemory_branch_flushAfter=True,max_dispatch_stores_per_cycle=2)
        profiles.append(item);add_digest(stream,item)
        for uid in new_uids:
            add_digest(stream,["actual_original_bytes_fire_then_dequeue",uid,actor.all[uid].position,actor.finish_ticks[uid]])
    assert actor.head==actor.tail==len(actor.completed)==256 and len(actor.cancelled)==256 and not actor.aborted
    save(path,"store_queue",profiles,stream,normal_store_uids=256,cancelled_store_uids=256,
         exact_absolute_position_reuses=256,actual_Sbuffer_fragments=256,resets_between_profiles=0)
