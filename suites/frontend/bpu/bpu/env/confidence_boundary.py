"""Normal read traffic holds TAGE while leaving auxiliary Main writes free."""
from suites.frontend.bpu.bpu.env.mixed_visibility import MixedVisibilityService
from suites.frontend.bpu.bpu.bundle.confidence_boundary import confidence_boundary_binding


class ConfidenceBoundaryService(MixedVisibilityService):
    def __init__(self,env,checks):
        super().__init__(env,checks,binding_factory=confidence_boundary_binding)

    async def submit_mixed_learning(self):
        # The visibility consumers temporarily visit other windows.
        # Restore the genuine loop before the long concurrent training burst.
        await self.query(self.checks.stream_pc)
        self.checks.arm_mixed()
        def capacity(_):
            # Foreground observation owns the first error. Do not poison a
            # pending transfer with the same error and rethrow it at teardown.
            if any(getattr(item,'failure',None) is not None for item in
                   (self.monitor,self.checks,self.env.checker)):return False
            main=self.env.checker.model.sources.main
            return main.offered is None and not any(q.pending for q in main.directions.values())
        # Queue all transfers normally. The existing driver's admission hook
        # regulates auxiliary capacity; cases never create tasks or sleeps.
        with self.agent.training_driver.admit_when(capacity):
            await self.submit(tuple((s,self.env.branch_path(o)) for s,o in
                zip(self.checks.requests[3:],self.checks.program.late_outcomes,strict=True)))
