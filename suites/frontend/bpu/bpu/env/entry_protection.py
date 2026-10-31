"""Real fallback-path originals and existing driver-owned flowing recovery."""
from suites.frontend.bpu.bpu.env.early_opposition import EarlyOppositionProgram
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.model.early_opposition import provider,main_counter
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect


class Program(EarlyOppositionProgram):
    actual_fallback=False

    async def restart(self,source):
        if not self.actual_fallback: return await super().restart(source)
        await self.pause(); self.checker.source_token(source)
        request=BpuRedirect(self.pc,source.meta.redirect,cfi_pc=self.checker.coverage.program.fallback_pc,
            taken=1,branch_type=2)
        self.checker.plan_redirect(source,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        return boundary

    async def confirmed_reward(self,source):
        checks=self.checker.coverage; owner=self.checker.source_token(source).sequence
        await self.observation.wait('named_interior_original_actual_reward',lambda _:
            any(row[0]==owner for row in checks.confirmed_increases) and checks.pending_effect is None)
        checks.reward_receipt(source)

    async def contradict(self,source):
        checks=self.checker.coverage; self.actual_fallback=True
        source=await self.steer_main(source,3)
        # A NEW fallback-path original gives both read and matching ancestry.
        # Reusing the taken-loop source after just one edge does not do this.
        source=await self.query(source)
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.pause()
        checks.before_flowing_recovery(source)
        await RecoveryDriver(self.agent,self.checker).send(source,
            position=checks.program.recovery_offset,branch_type=2)
        def wrong(token):
            value=provider(self.checker.model.sources,token)
            return (value is not None and value.key==checks.protected and value.counter<4
                and main_counter(token)==3 and token.middle.branch.position==2 and token.middle.branch.taken)
        result=await self.consume('interior_original_NT_contradicted_by_Main',wrong)
        owner=self.checker.source_token(result).sequence
        await self.observation.wait('named_interior_original_actual_penalty',lambda _:
            any(row['owner']==owner for row in checks.losses) and checks.pending_loss is None)
        checks.wrong_receipt(result)
        return result
