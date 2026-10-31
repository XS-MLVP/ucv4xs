"""Original sources, concurrent production-driver sends and predicate waits."""
from contextlib import asynccontextmanager
from suites.frontend.bpu.bpu.bundle.main_service import main_service_binding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from suites.frontend.bpu.bpu.env.branch_targets import BranchTargetProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.main_service import PCS,PEER_POSITION,POSITION,STREAM_PC,old_target,new_target,peer_target
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect,BpuBatchTraining,BpuBranchFeedback


def branch(position,target,kind,*,taken=True,wrong=False):
    return BpuBranchFeedback(position,target,kind,taken=int(taken),mispredict=int(wrong))


def resolved_pair(pc,target,*,wrong=False):
    return (branch(PEER_POSITION,peer_target(pc),1,taken=False),branch(POSITION,target,3,wrong=wrong))


class MainProgram(BranchTargetProgram):
    async def capture(self,pc,verify):
        await self.pause();request=BpuRedirect(pc,self.anchor.meta.redirect,cfi_pc=self.pc+4)
        self.checker.plan_redirect(self.anchor,request);boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        verify(source);await self.pause();return source


@asynccontextmanager
async def main_program(agent):
    phr=BpuPhrChecker(scope='autonomous Micro/Main and complete source-owned target service')
    async with PipelineObservation(agent,sources=BranchTargetSources()) as observation,agent.observe_phr(phr):
        await agent.reset(PCS[0]);anchor=await agent.next_transaction(start_pc=PCS[0])
        await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,sc=False,ittage=False,ras=False,settle=True)
        yield MainProgram(agent,observation,anchor,PCS[0]);phr.summary()


async def prepare(environment):
    loop=await environment.capture_source(STREAM_PC)
    await environment.resolve(loop,branch(POSITION,STREAM_PC,2,wrong=True))
    cold=[]
    for pc in PCS:
        source=await environment.capture_source(pc);cold.append(source)
        await environment.resolve(source,branch(POSITION,old_target(pc),3,wrong=True),retire=False)
        source=await environment.capture_source(pc)
        await environment.resolve(source,branch(PEER_POSITION,peer_target(pc),1,wrong=True))
        source=await environment.capture_source(pc)
        await environment.resolve(source,branch(PEER_POSITION,peer_target(pc),1,taken=False,wrong=True),
            branch(POSITION,old_target(pc),3))
        source=await environment.capture_source(pc)
        await environment.resolve(source,*resolved_pair(pc,old_target(pc)))
    current=tuple([await environment.capture_source(pc) for pc in PCS])
    return tuple(cold),current


class MainService:
    def __init__(self,environment,checks):
        self.env,self.agent,self.checks=environment,environment.agent,checks
        self.monitor=ServiceMonitor(self.agent,checks,binding=main_service_binding(self.agent,
            alignment=checks.alignment,bank=checks.bank))

    async def __aenter__(self):await self.monitor.__aenter__();return self
    async def __aexit__(self,*exc):return await self.monitor.__aexit__(*exc)

    async def query(self,pc):
        request=BpuRedirect(pc,self.env.anchor.meta.redirect,cfi_pc=self.env.pc+4)
        self.env.checker.plan_redirect(self.env.anchor,request);tick=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=tick)
        self.env.checker.source_token(source);self.monitor.raise_failure();return source

    async def start(self):
        loop=await self.query(STREAM_PC)
        self.checks.start(loop)

    async def submit(self,sources):
        transactions=[]
        for source,pc in zip(sources,self.checks.pcs,strict=True):
            outcomes=(branch(PEER_POSITION,new_target(pc),3,wrong=True),) if self.checks.reclassify else (
                (branch(POSITION,new_target(pc),3,wrong=True),) if self.checks.stale else resolved_pair(pc,new_target(pc),wrong=True))
            tx=BpuBatchTraining(pc,source.meta.resolve,outcomes)
            self.env.checker.plan_feedback(source,tx);transactions.append(tx)
        before=self.env.checker.last_tick;handles=tuple(self.agent.training_driver.send(tx) for tx in transactions)
        def healthy():self.monitor.raise_failure();return True
        try:
            await self.env.observation.wait('main_original_inputs_accepted',lambda _:healthy() and all(h.done() for h in handles))
            ticks=tuple([(await h).tick for h in handles])
            accepted=tuple(sorted({tick:r for s in sources for tick,r in self.env.checker.resolutions_for_source(s)
                if tick>before}.items()))
            self.checks.check(ticks,tuple(t for t,_ in accepted),'all production sends have exact original accepts')
            self.checks.accepted_burst(accepted)
            await self.env.observation.wait('main_learning_mature_but_service_blocked',lambda c:healthy()
                and c.model.sources.main.offered is None and not any(c.model.sources.main.entry_offers.values()))
            self.checks.pending()
        finally:
            for h in handles:
                if not h.done() and h.accepted_event is None:h.cancel()

    async def release(self):
        self.checks.release();await self.env.pause()
        def complete(_):
            self.monitor.raise_failure();return tuple(map(len,self.checks.written))==self.checks.service_shape
        await self.env.observation.wait('main_all_actual_services',complete)
