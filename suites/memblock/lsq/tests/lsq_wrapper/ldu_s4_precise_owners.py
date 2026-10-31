"""New precise ROB-head program; frozen old drivers/results remain unchanged."""
from dataclasses import replace
import json
from pathlib import Path

from suites.memblock.lsq.lsq_wrapper.types import Address, Data
from suites.memblock.lsq.psq.types import Attributes
from suites.memblock.lsq.replay.types import Refill
from suites.memblock.lsq.vlq.types import Redirect
from .ldu_s4_plain_owners import HIT, PF, MISS, PATTERNS as OLD_PATTERNS, OrdinaryS4Program
from .memory_owners import cached_load
from .mixed_owners import rob_pointer
from .s4_precise_check import PreciseCheck, rob


PATTERNS={**OLD_PATTERNS,"both_pf":(PF,PF),"both_miss":(MISS,MISS)}
LEGAL_CASES=tuple((page,name) for page in(False,True) for name,events in PATTERNS.items()
                  if page or events[0].tlb_page_fault==events[1].tlb_page_fault)
assert len(LEGAL_CASES)==24


class PreciseOrdinaryS4Program(OrdinaryS4Program):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.young=cached_load(self.start_lq+2,rob_pointer(self.start_rob+4),self.start_sq+1,0x4803C,0xA34803C)
        self.checker=PreciseCheck(self.start_sq,self.start_lq,self.start_rob,self.sequence)
        self.boot_records=self.env.journal.records
        self.boot_tick=self.env.last_tick
        self.finished_report=None

    async def cycle(self,**fields):
        packet=replace(self.base,attributes=(Attributes(),Attributes()),**fields)
        await super().cycle(**fields)
        self.checker.observe(packet,self.env.pre_observed,self.env.observed,self.env.last_tick)

    async def split(self,load,pattern,*,feedback=False):
        self.last_cache_events=pattern
        self.checker.declare(load,pattern,self.lane,self.env.last_tick+2,feedback)
        return await super().split(load,pattern,feedback=feedback)

    async def grant(self,packet):
        if packet.execution.causes==1<<6:
            if not self.last_cache_events[1].miss:self.checker.background_prefetch(9)
            await self.cycle(refills=(Refill(True,9),Refill()))
            for _ in range(3):
                assert not any(self.env.observed[f"io_replay_{b}_valid"] for b in range(3))
                await self.cycle()
            await self.cycle(refills=(Refill(True,3),Refill()))
        elif packet.execution.handled:
            await self.cycle(refills=(Refill(True,packet.execution.mshr),Refill()))
        for _ in range(80):
            bank=next((b for b in range(3) if self.env.observed[f"io_replay_{b}_valid"]),None)
            if bank is not None:break
            await self.cycle()
        else:raise AssertionError("original S4 owner never actually granted after its declared external jobs")
        await self.cycle(replay_ready=tuple(b==bank for b in range(3)))

    async def execute_older(self):
        if not self.address:
            addresses,data=[Address(),Address()],[Data(),Data()]
            addresses[self.lane%2],data[1-self.lane%2]=self.store.address(),self.store.data()
            await self.cycle(addresses=tuple(addresses),data=tuple(data))
            for _ in range(3):await self.cycle()
        old=next(s for s in self.loads if s["load"] is self.blocker)
        if not old["sent"]:await self.clean_aligned(self.blocker)
        for _ in range(30):
            if old["complete"]:break
            await self.cycle()
        assert old["complete"] and self.executed_store and self.data

    async def trap_and_reuse(self):
        packet=self.last_packet
        assert packet.exceptions and packet.update_address
        await self.execute_older()
        # Backend may retire the older prefix, but must NOT retire this fault.
        self.base=replace(self.base,pending=self.target.execution.uop.rob,pending_next=self.target.execution.uop.rob)
        for _ in range(8):await self.cycle()
        assert self.consumed is None and not self.store_done,"ROB retirement is not Sbuffer completion"
        target=next(s for s in self.loads if s["load"] is self.target)
        assert target["complete"]==bool(not packet.execution.need_replay)
        victims=[s for s in self.loads if not s["complete"] and not s["cancelled"] and
                 (rob(s["load"].execution.uop.rob)-rob(self.target.execution.uop.rob))%640<320]
        expected=self.start_lq+3-len(victims)
        await self.cycle(redirect=Redirect(True,self.target.execution.uop.rob,True))
        for s in victims:s["cancelled"]=True;self.cancelled.append(s)
        observed=None
        for _ in range(50):
            await self.cycle()
            p=self.env.observed
            if p["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                observed=120*p["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+p["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
            if observed is not None and not(p["io_toLsqEnqCtrl_lqRecoverStall"] or p["io_toLsqEnqCtrl_sqRecoverStall"]):break
        assert observed==expected%240 and self.checker.recovery is None
        for _ in range(4):await self.cycle()
        self.base=replace(self.base,pending=rob_pointer(self.start_rob+5),pending_next=rob_pointer(self.start_rob+5))
        replacements=[cached_load(expected+n,rob_pointer(self.start_rob+5+n),self.start_sq+1,
                                   0x4703C+64*n,0xA24703C+64*n) for n in range(len(victims))]
        assert 1<=len(replacements)<=2
        await self.dispatch(replacements)
        return replacements

    async def finish_precise(self,replacements):
        await self.execute_older()
        for load in replacements:await self.split(load,(HIT,HIT))
        for _ in range(4):await self.cycle()
        self.base=replace(self.base,pending=rob_pointer(self.start_rob+8),pending_next=rob_pointer(self.start_rob+8),sbuffer_ready=(True,True))
        for _ in range(100):
            await self.cycle()
            if self.store_done and all(s["complete"] or s["cancelled"] for s in self.loads):break
        assert self.store_done and all(s["complete"] or s["cancelled"] for s in self.loads)
        for _ in range(12):await self.cycle()
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"] and not self.env.observed["io_replayAllocate"]
        self.finished_report=self.checker.finish()
        self.finished_report["native_prefix_records"]=self.boot_records
        self.finished_report["native_prefix_last_tick"]=self.boot_tick
        self.finished_report["native_records_at_end"]=self.env.journal.records
        assert len(self.loads)+1==self.finished_report["allocated_UIDs"]
        return self.finished_report

    async def run_program(self,pattern):
        await self.dispatch([self.blocker,self.target,self.young],store=True)
        packet=await self.split(self.target,pattern)
        if packet.execution.need_replay and not packet.update_address:
            await self.grant(packet)
            retry=tuple(replace(e,mshr_nack=False,miss=False) for e in pattern)
            packet=await self.split(self.target,retry,feedback=True)
            assert not packet.execution.need_replay and packet.update_address
        replacements=await self.trap_and_reuse() if packet.exceptions else [self.young]
        return await self.finish_precise(replacements)

    def write_report(self,*,case,passed,error=None):
        result=dict(nodeid=self.env.nodeid,case=case,passed=passed,error=error,
                    native_boot_records=self.boot_records,
                    independent_online_checks=self.finished_report if passed else dict(counts=dict(self.checker.counts),unfinished=True,
                        partial_UIDs=[{k:s[k] for k in("uid","order","kind","pos","released","cancelled","trapped","fault_wb","pending_replay")}
                                      for s in self.checker.program],
                        limits="partial public ledger only, not a completed terminal disposition"),
                    diagnostics="default summaries only; no per-cycle JSON or waveforms")
        path=Path(self.env.journal.name).with_name("s4-precise-summary.json")
        with path.open("x") as out:out.write(json.dumps(result,indent=2)+"\n")
