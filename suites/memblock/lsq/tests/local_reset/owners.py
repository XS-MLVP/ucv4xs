"""Retained external requests are not aborted by the local LSQ reset."""
from dataclasses import replace
import json
from pathlib import Path

from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.types import Bypass, Load
from lsqverify.lsq_wrapper.types import Bus, Dispatch, Inputs
from lsqverify.rar.types import Query as RarQuery
from lsqverify.raw.types import Query as RawQuery
from tests.lsq_wrapper.memory_owners import cached_load
from tests.lsq_wrapper.mixed_owners import rob_pointer
from .check import LocalResetCheck


class RetainedUncacheProgram:
    def __init__(self,env,lane,phase):
        self.env,self.lane,self.phase=env,lane,phase
        self.base=Inputs(pending=rob_pointer(8),pending_next=rob_pointer(8),bus=Bus(outstanding=True))
        self.checker=LocalResetCheck();self.boot_records=env.journal.records;self.report=None
        self.old_sid=15-lane;self.new_sid=12-lane
        self.old_returned=False;self.old_response=dict(response=True,response_id=self.old_sid,data=0xDEADBEEF12340000+lane,
                                                       error=bool(lane%2),nderr=not bool(lane%2))

    def lanes(self,value,empty):return tuple(value if n==self.lane else empty for n in range(3))

    async def cycle(self,**fields):
        packet=replace(self.base,**fields)
        await self.env.cycle(packet)
        self.checker.observe(packet,self.env.pre_observed,self.env.observed,self.env.last_tick)

    async def idle(self,n):
        for _ in range(n):await self.cycle()

    @staticmethod
    def load(position,order,tag):
        load=cached_load(position,rob_pointer(order),0,0x610000+0x1000*tag,0xE0610000+0x1000*tag)
        return replace(load,execution=replace(load.execution,nc=True,need_replay=True,causes=1,aligned_type=3,
                                              last_beat=bool(load.paddr&64)),update_address=False,hyper=False,nonleaf=False,gpaddr=0)

    async def dispatch(self,load):
        d=Dispatch(True,1,load.execution.uop.rob,1,load_start=load.execution.uop.lq)
        await self.cycle(dispatch=(d,)+(Dispatch(),)*7)

    async def initial(self,load):
        u=load.execution.uop
        await self.cycle(queries=self.lanes(Query(True,load.execution.vaddr,u.sq,3),Query()))
        await self.cycle(translations=self.lanes(Translation(load.paddr),Translation()))
        await self.cycle(rar_queries=self.lanes(RarQuery(True,u.rob,u.lq,load.paddr,False,False),RarQuery()),
                         raw_queries=self.lanes(RawQuery(True,u.rob,u.sq,load.paddr,255,False,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        revoke=self.lanes(True,False)
        await self.cycle(loads=self.lanes(load,Load()),rar_revoke_last=revoke,raw_revoke_last=revoke)

    async def accept(self,load,sid):
        for _ in range(80):
            if self.env.observed["io_uncache_req_valid"]:break
            await self.cycle()
        else:raise AssertionError("original NC request never became visible")
        assert self.env.observed["io_uncache_req_bits_addr"]==load.paddr
        mid=self.env.observed["io_uncache_req_bits_id"]
        await self.cycle(bus=replace(self.base.bus,ready=True))
        await self.cycle(bus=replace(self.base.bus,ack=True,mid=mid,sid=sid))
        return mid

    async def old_return(self):
        assert not self.old_returned
        await self.cycle(bus=replace(self.base.bus,**self.old_response));self.old_returned=True

    async def new_return(self,sid,value):
        await self.cycle(bus=replace(self.base.bus,response=True,response_id=sid,data=value))

    async def grant(self,load):
        for _ in range(80):
            bank=next((b for b in range(3) if self.env.observed[f"io_replay_{b}_valid"]),None)
            if bank is not None:break
            await self.cycle()
        else:raise AssertionError("actual new response did not grant its original owner")
        p=f"io_replay_{bank}_bits_"
        assert self.env.observed[p+"uop_lqIdx_value"]==load.execution.uop.lq.value
        slot=self.env.observed[p+"replayQueueIdx"]
        await self.cycle(replay_ready=tuple(b==bank for b in range(3)))
        return slot

    async def finish_load(self,load,slot,*,old_in_s1=False,assert_empty=True):
        u=load.execution.uop
        await self.cycle(queries=self.lanes(Query(True,load.execution.vaddr,u.sq,3),Query()),
                         bypass=self.lanes(Bypass(True,u.lq,True,False),Bypass()))
        bus=replace(self.base.bus,**self.old_response) if old_in_s1 else self.base.bus
        await self.cycle(translations=self.lanes(Translation(load.paddr),Translation()),bus=bus)
        if old_in_s1:
            assert not self.old_returned;self.old_returned=True
        await self.cycle(rar_queries=self.lanes(RarQuery(True,u.rob,u.lq,load.paddr,True,True),RarQuery()),
                         raw_queries=self.lanes(RawQuery(True,u.rob,u.sq,load.paddr,255,True,u.rvc,u.ftq,u.offset,u.checkpoint),RawQuery()))
        q=replace(load.execution,replay_feedback=True,slot=slot,need_replay=False,causes=0)
        await self.cycle(loads=self.lanes(replace(load,execution=q,update_address=True),Load()))
        await self.idle(8)
        if assert_empty:assert self.env.observed["io_lqEmpty"] and not self.env.observed["io_replayAllocate"]

    async def run(self):
        old=self.load(0,10,0)
        await self.dispatch(old);await self.initial(old);old_mid=await self.accept(old,self.old_sid)
        for _ in range(6):await self.cycle(reset=True)
        await self.idle(8)
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]
        if self.phase=="empty_after_reset":await self.old_return();await self.idle(8)
        fresh=self.load(0,20,1)
        await self.dispatch(fresh);await self.initial(fresh);fresh_mid=await self.accept(fresh,self.new_sid)
        assert old_mid==fresh_mid,"actual reset structure MID must be reused, not merely another entry"
        if self.phase=="new_mid_wait_response":
            await self.old_return();await self.idle(8)
            assert not any(self.env.observed[f"io_replay_{b}_valid"] for b in range(3))
        await self.new_return(self.new_sid,0x1122334455667700+self.lane)
        if self.phase=="new_response_wait_bypass":await self.old_return();await self.idle(8)
        slot=await self.grant(fresh)
        await self.finish_load(fresh,slot,old_in_s1=self.phase=="new_bypass_s1")
        assert self.old_returned
        # Reuse SID immediately after its real old response, not after any
        # data consumption by the reset-aborted old Load (which never occurs).
        final=self.load(1,22,2)
        await self.dispatch(final);await self.initial(final);await self.accept(final,self.old_sid)
        await self.new_return(self.old_sid,0x8877665544332200+self.lane)
        await self.finish_load(final,await self.grant(final))
        await self.idle(8)
        assert not self.env.observed["io_uncache_req_valid"] and not self.env.observed["io_ldExceptionInfo_valid"]
        self.report=self.checker.finish()
        assert len(self.report["UIDs"])==3 and len(self.report["external_jobs"])==3
        return self.report

    def write(self,passed,error=None):
        result=dict(nodeid=self.env.nodeid,passed=passed,error=error,lane=self.lane,phase=self.phase,native_boot_records=self.boot_records,
                    online_check=self.report if passed else dict(counts=dict(self.checker.counts),events=self.checker.events,unfinished=True),
                    scope="full-output WrapperEnv plus independent public-effect checker; retained external NC profile, not native SoC reset proof")
        with Path(self.env.journal.name).with_name("local-reset-summary.json").open("x") as f:f.write(json.dumps(result,indent=2)+"\n")
