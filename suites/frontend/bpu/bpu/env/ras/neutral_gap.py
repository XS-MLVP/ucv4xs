"""Real program sources exercise omitted-notification lifetime recovery."""
from contextlib import asynccontextmanager
from suites.frontend.bpu.runtime.wait import wait_condition
from suites.frontend.bpu.bpu.env.ras.semantic import RasSemanticEnvironment
from suites.frontend.bpu.bpu.env.ras.retirement import BpuRetirement
from suites.frontend.bpu.bpu.env.ras.program import collect,learn_sites
from suites.frontend.bpu.bpu.checker.ras.neutral_gap import RasNeutralGapChecks
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.model.ras.capacity import CAPACITY,OLD_CALL,NEW_CALL,NEW_RETURN,RESUMED_CALLS
from suites.frontend.bpu.bpu.model.ras.neutral_gap import HOLD_DISTANCE,NEUTRAL


class RasNeutralGapProgram:
    def __init__(self,agent,semantic,retirement):
        self.agent,self.semantic,self.retirement=agent,semantic,retirement
        self.checks=semantic.reference

    async def redirect(self,source,pc,*,guarded=False):
        program=self.checks.owned_program(source)
        boundary=await self.semantic.wait(self.agent.redirect(BpuRedirect(pc,source.meta.redirect)),'redirect from exact genuine source')
        def sample():
            self.checks.raise_failure()
            return self.checks.model.program,self.checks.model.pending_recovery,self.checks.model.guarded
        await self.semantic.wait(wait_condition(self.agent.dut.clock,sample=sample,
            satisfied=lambda state:state==(program,None,guarded),
            name='ras.neutral-gap-source-recovery',timeout_cycles=128),'owned program and resource state compared')
        return boundary

    async def stream(self,source,pc,action,minimum,*,guarded=False):
        boundary=await self.redirect(source,pc,guarded=guarded)
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'allow real program instructions')
        return await collect(self.retirement,self.semantic,pc,action,minimum,boundary)

    async def prepare(self):
        sources=await learn_sites(self.retirement,self.semantic,OLD_CALL,((OLD_CALL,OLD_CALL,2,2),
            (NEUTRAL,NEUTRAL,2,0),(NEW_CALL,NEW_CALL,2,2),(NEW_RETURN,0x4001f000,3,1)))
        # Cold preparation ran with RAS disabled. Start from its genuine reset
        # checkpoint; do not label it an enabled speculative call source.
        boundary=await self.semantic.wait(self.agent.redirect(BpuRedirect(OLD_CALL,sources[OLD_CALL].meta.redirect)),
            'start old call program from genuine cold checkpoint')
        await self.semantic.wait(self.agent.set_ready(prediction=True,meta=True),'allow real old calls')
        self.originals=await collect(self.retirement,self.semantic,OLD_CALL,2,CAPACITY+2,boundary)
        self.checks.filled(self.originals)

    async def threshold(self):
        neutral=await self.stream(self.originals[HOLD_DISTANCE],NEUTRAL,0,1)
        self.checks.neutral(neutral,calls=HOLD_DISTANCE)
        await self.semantic.wait(self.retirement.retire_many([(neutral[-1],0)]),'real distance-two neutral retirement')
        self.checks.held()
        resumed=await self.stream(neutral[-1],OLD_CALL,2,CAPACITY-HOLD_DISTANCE+2)
        self.checks.filled(resumed,start=HOLD_DISTANCE)
        return resumed[-1]

    async def reclaim(self,source):
        neutral=await self.stream(source,NEUTRAL,0,1,guarded=True)
        self.checks.neutral(neutral,calls=CAPACITY)
        await self.semantic.wait(self.retirement.retire_many([(neutral[-1],0)]),'real guarded-gap neutral retirement')
        def sample():
            self.checks.raise_failure()
            return self.checks.resources[-1] if self.checks.resources else None
        await self.semantic.wait(wait_condition(self.agent.dut.clock,sample=sample,
            satisfied=lambda row:row is not None and row['bos']==CAPACITY-1 and not row['guarded'],
            name='ras.neutral-reclamation-compared',timeout_cycles=128),'actual registered guard release')
        self.checks.reclaimed()
        return neutral[-1]

    async def reuse(self,source):
        new=await self.stream(source,NEW_CALL,2,RESUMED_CALLS)
        self.checks.reused(new)
        returns=await self.stream(new[-1],NEW_RETURN,1,1)
        self.checks.returned(returns)


@asynccontextmanager
async def ras_neutral_gap_program(agent,coverage):
    checks=RasNeutralGapChecks(coverage)
    async with RasSemanticEnvironment(agent,reference=checks,observe_resources=True) as semantic,BpuRetirement(agent,semantic=checks) as retirement:
        yield RasNeutralGapProgram(agent,semantic,retirement)
