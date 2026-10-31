"""Async public feedback and SDK-confirmed target service stay below the case."""
from suites.frontend.bpu.bpu.bundle.indirect_service import indirect_service_binding
from suites.frontend.bpu.bpu.monitor.service import ServiceMonitor
from suites.frontend.bpu.bpu.model.ittage_service import PC,POSITION,PATHS,TARGETS,STREAM_PC
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect,BpuBatchTraining,BpuBranchFeedback


async def prepare_targets(environment,table):
    for path,target in zip(PATHS,TARGETS,strict=True):
        source=await environment.cold_source(PC,table=table,via=path)
        token=environment.checker.source_token(source)
        expected=environment.checker.model.sources.snapshot(token,resolved=True)
        environment.checker.board.check(expected=True,actual=expected.late.branch.target!=target)
        await environment.resolve(source,BpuBranchFeedback(POSITION,target,3,taken=1,mispredict=1))
        environment.checker.retire_source(source.meta_tick)


async def prepare_stream(environment):
    source=await environment.capture_source(STREAM_PC)
    await environment.resolve(source,BpuBranchFeedback(POSITION,STREAM_PC,2,taken=1,mispredict=1))
    environment.checker.retire_source(source.meta_tick)


class IndirectService:
    def __init__(self,environment,checks):
        self.env,self.agent,self.checks=environment,environment.agent,checks
        self.monitor=ServiceMonitor(self.agent,checks,binding=indirect_service_binding(self.agent,
            table=checks.table,bank=checks.bank,include_retention=checks.observe_retention))

    async def __aenter__(self):await self.monitor.__aenter__();return self
    async def __aexit__(self,*exc):return await self.monitor.__aexit__(*exc)

    async def query(self,pc,*,origin=None,cfi=None):
        origin=self.env.anchor if origin is None else origin
        request=BpuRedirect(pc,origin.meta.redirect,cfi_pc=self.env.pc+4 if cfi is None else cfi)
        self.env.checker.plan_redirect(origin,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=boundary)
        self.env.checker.source_token(source);self.monitor.raise_failure();return source

    async def query_path(self,path):
        if path is None:return await self.query(PC)
        via=await self.query(path);source=await self.query(PC,origin=via,cfi=path+4)
        self.env.checker.retire_source(via.meta_tick);return source

    async def start(self):await self.query(STREAM_PC);self.checks.begin_read_window()

    async def submit(self,sources):
        transactions=[]
        for source,target in zip(sources,TARGETS,strict=True):
            tx=BpuBatchTraining(PC,source.meta.resolve,(BpuBranchFeedback(POSITION,target,3,taken=1,mispredict=0),))
            self.env.checker.plan_feedback(source,tx);transactions.append(tx)
        before=self.env.checker.last_tick
        handles=tuple(self.agent.training_driver.send(tx) for tx in transactions)
        def healthy():self.monitor.raise_failure();return True
        try:
            await self.env.observation.wait('all_indirect_inputs_accepted',lambda _:healthy() and all(h.done() for h in handles))
            ticks=tuple([(await handle).tick for handle in handles])
            accepted=tuple(sorted({tick:request for source in sources
                for tick,request in self.env.checker.resolutions_for_source(source) if tick>before}.items()))
            self.checks.check(ticks,tuple(tick for tick,_ in accepted),'every asynchronous send has its exact actual acceptance')
            self.checks.accepted_burst(accepted)
            await self.env.observation.wait('indirect_learning_mature_but_service_blocked',lambda checker:healthy()
                and checker.model.sources.indirect.learning is None and not checker.model.sources.indirect.normal)
            self.checks.pending()
        finally:
            for handle in handles:
                if not handle.done() and handle.accepted_event is None:handle.cancel()

    async def release(self):
        self.checks.release();await self.env.pause()
        def finished(_):self.monitor.raise_failure();return len(self.checks.written)==4
        await self.env.observation.wait('all_actual_indirect_target_commits',finished)
