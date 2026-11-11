"""Direction return and public source association stay below the scenario."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.early_opposition import EarlyOppositionProgram
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import ahead_owner
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import steady_history
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import FALLBACK


class EarlyPositiveProgram(EarlyOppositionProgram):
    async def negative_base(self,source,checks):
        await self.restart(source)
        def negative(token):
            owner=ahead_owner(self.checker.model.sources,token)
            return owner is not None and owner[1]==0 and steady_history(token,FALLBACK)
        return await self.consume('same_ahead_owner_negative_preserves_positive_seed',negative)

    async def positive_opposed(self,source,checks):
        await self.pause()
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.restart(source)
        def positive(token):
            return checks.qualifies_current_source(self.checker.model.sources,token)
        try:result=await self.consume('positive_provider_overrides_negative_base',positive)
        except TimeoutError:
            checks.check(True,False,dict(point='positive provider precondition did not reach a public consumer',
                seeds=checks.protected_positive,first_returns=checks.return_candidates))
        checks.positive_consumer(result)
        token=self.checker.source_token(result)
        await self.observation.wait('positive_original_source_actual_useful_increase',lambda _:
            any(row[0]==token.sequence for row in checks.confirmed_increases) and checks.pending_effect is None)
        return result
