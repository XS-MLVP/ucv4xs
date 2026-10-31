"""Normal semantic preparation and existing asynchronous admission, no sleeps."""
from suites.frontend.bpu.bpu.env.direction_service import DirectionService
from suites.frontend.bpu.bpu.bundle.retouch_replacement import retouch_replacement_binding
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,resolved_path
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight


async def prepare_retouch_replacement(env,checks):
    await env.prepare_direction_pair(checks.prepared)
    for path in checks.program.paths[1:]:await env.prepare_direction_history(path,checks.prepared)
    source=await env.capture_source(PC)
    await env.resolve(source,*env.branch_path(resolved_path()))
    after=await env.capture_source(PC);checks.prepared(after,((0,3),(1,6)))
    env.checker.retire_source(source.meta_tick);env.checker.retire_source(after.meta_tick)
    sources=[]
    for history in checks.program.feedback_order:
        path=checks.program.paths[history]
        sources.append(await env.capture_source(PC) if path is None else await env.capture_via(PC,path))
    checks.arm(tuple(sources))


class RetouchReplacementService(DirectionService):
    def __init__(self,env,checks):
        super().__init__(env,checks,binding_factory=retouch_replacement_binding)

    async def submit_program(self):
        def admitted(transaction):
            if any(getattr(item,'failure',None) is not None for item in
                   (self.monitor,self.checks,self.env.checker)):return False
            main=self.env.checker.model.sources.main
            if main.offered is not None or any(q.pending for q in main.directions.values()):return False
            if transaction.resolve_meta is self.checks.sources[-1].meta.resolve:
                active=bool(learning_inflight(self.env.checker.model.sources.tage))
                if self.checks.program.mode=='settled' and active:return False
                self.checks.last_launch=dict(tick=self.env.checker.last_tick,learning_inflight=active)
            return True
        with self.agent.training_driver.admit_when(admitted):
            await self.submit(tuple((s,self.env.branch_path(self.checks.program.branch_outcomes(i)))
                                    for i,s in enumerate(self.checks.sources)))
