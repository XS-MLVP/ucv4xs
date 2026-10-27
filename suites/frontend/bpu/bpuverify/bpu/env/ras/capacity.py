"""Real MainBTB programs, owned rollback and ordered production retirement."""
from contextlib import asynccontextmanager
from bpuverify.common.env.wait import wait_condition
from bpuverify.bpu.env.ras.semantic import RasSemanticEnvironment
from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.checker.ras.capacity import RasReuseChecks
from bpuverify.bpu.env.ras.program import collect,learn_sites
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.model.ras.capacity import CAPACITY,PRESERVED,OLD_CALL,OLD_RETURN,NEW_CALL,NEW_RETURN,RESUMED_CALLS


class RasReuseProgram:
    def __init__(self,agent,semantic,retirement):
        self.agent,self.semantic,self.retirement=agent,semantic,retirement
        self.checks=semantic.reference

    async def prepare(self):
        a=self.agent;s=self.semantic
        sources=await learn_sites(self.retirement,s,OLD_CALL,((OLD_CALL,OLD_CALL,2,2),(OLD_RETURN,0x4001f000,3,1),
            (NEW_CALL,NEW_CALL,2,2),(NEW_RETURN,0x4001f000,3,1)))
        old=sources[OLD_CALL]
        boundary=await s.wait(a.redirect(BpuRedirect(OLD_CALL,old.meta.redirect)),'start old self-call stream')
        await s.wait(a.set_ready(prediction=True,meta=True),'allow real old calls')
        self.originals=await collect(self.retirement,s,OLD_CALL,2,CAPACITY+2,boundary)
        self.checks.filled(self.originals)

    async def restore(self,source,target):
        program=self.checks.owned_program(source);before=len(self.checks.restores)
        boundary=await self.semantic.wait(self.agent.redirect(BpuRedirect(target,source.meta.redirect)),'restore exact genuine source')
        def sample():
            self.checks.raise_failure()
            return self.checks.model.program,self.checks.model.pending_recovery,len(self.checks.restores),self.checks.model.guarded
        await self.semantic.wait(wait_condition(self.agent.dut.clock,sample=sample,
            satisfied=lambda state:state[0]==program and state[1] is None and state[2]>before and not state[3],
            name='ras.real-source-recovery-compared',timeout_cycles=128),'registered source recovery')
        return boundary,program

    async def guarded(self):
        boundary=await self.semantic.wait(self.agent.redirect(BpuRedirect(OLD_RETURN,self.originals[-1].meta.redirect)),
            'same-current source cannot release guarded RAS')
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'offer genuine guarded returns')
        guarded=await collect(self.retirement,self.semantic,OLD_RETURN,1,3,boundary)
        self.checks.guarded_returns(guarded)
        source=self.originals[PRESERVED]
        boundary,program=await self.restore(source,OLD_RETURN);self.checks.recovered(source,program)
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'allow recovered real old returns')
        returns=await collect(self.retirement,self.semantic,OLD_RETURN,1,2,boundary)
        self.checks.check(True,len(returns)>=2,'younger old-return suffix exists')
        # Undo the last speculative return; only the older real returns retire.
        boundary,_=await self.restore(returns[-1],NEW_CALL)
        surviving=self.originals[:PRESERVED];kept=returns[:-1]
        await self.semantic.wait(self.retirement.retire_many([(s,2) for s in surviving]+[(s,1) for s in kept]),
            'retire only surviving old calls and returns')
        self.checks.old_retired(surviving,kept)
        return boundary

    async def reuse(self,boundary):
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'accept different-address new call versions')
        resumed=await collect(self.retirement,self.semantic,NEW_CALL,2,RESUMED_CALLS,boundary)
        self.checks.reused(resumed)
        boundary,_=await self.restore(resumed[-1],NEW_RETURN)
        kept=resumed[:-1]
        await self.semantic.wait(self.retirement.retire_many([(s,2) for s in kept]),'retire kept new versions exactly once')
        self.checks.new_retired(kept,resumed[-1])
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'consume new live return chain after wrap')
        returns=await collect(self.retirement,self.semantic,NEW_RETURN,1,1,boundary)
        await self.semantic.wait(self.retirement.retire_many([(s,1) for s in returns]),'retire fresh new-address returns')
        self.checks.final_returns(returns)


@asynccontextmanager
async def ras_reuse_program(agent,coverage):
    checks=RasReuseChecks(coverage)
    async with RasSemanticEnvironment(agent,reference=checks) as semantic,BpuRetirement(agent,semantic=checks) as retirement:
        yield RasReuseProgram(agent,semantic,retirement)
