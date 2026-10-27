"""Normal backend outcomes change Main while source-qualified fast learning stays live."""
from contextlib import asynccontextmanager
from bpuverify.bpu.env.early_positive import EarlyPositiveProgram
from bpuverify.bpu.model.early_opposition import main_counter, steady_history, provider, CONDITIONAL, FALLBACK
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.path_history import WIDTH, LAYOUT, SHIFT
from bpuverify.utage.model.semantic import HISTORIES
from bpuverify.bpu.coverage.early_aging import AGE_RULES
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.monitor.early_aging import EarlyAgingDiagnostics


class EarlyAgingProgram(EarlyPositiveProgram):
    async def restart(self, source):
        await self.pause()
        token = self.checker.source_token(source)
        require_recovery_window(self.checker.model.history.taken_edges, token.history.taken_edges,
            capacity=WIDTH, history_bits=max(length for length, _ in LAYOUT), shift=SHIFT)
        return await super().restart(source)

    async def original_positive_after_aging(self, source, checks):
        _, _, seed = checks.history_seeds[True]
        # The old seed is evidence only. Its circular PHR checkpoint may no
        # longer exist after hundreds of edges; recover using a FRESH owner.
        await self.restart(source)
        def positive(token):
            value = provider(self.checker.model.sources, token)
            return (value is not None and value.counter >= 4
                    and (value.key, value.tag, value.position) == (seed.key, seed.tag, seed.position))
        return await self.consume('saved_taken_provider_identity_consumed_after_maintenance', positive)

    async def stable_positive(self, source):
        await self.restart(source)
        def positive(token):
            value = provider(self.checker.model.sources, token)
            return (steady_history(token, CONDITIONAL) and value is not None and value.counter >= 4)
        return await self.consume('stable_independently_learned_taken_history', positive)

    async def highest_provider_error(self, source, checks):
        # Build the short-history fallback suffix with NEW owned recoveries,
        # not an expired old checkpoint or a write to folded-history state.
        await self.pause()
        await self.agent.configure_predictors(abtb=False, settle=True)
        for _ in range(max(HISTORIES) // SHIFT + 2):
            source = await self.query(source)
            if steady_history(self.checker.source_token(source), FALLBACK):
                break
        else:
            raise AssertionError('fresh fallback recoveries did not establish the original provider history')
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(source)
        await self.observation.wait('actual_owned_highest_provider_failure',
            lambda _: AGE_RULES[0] in checks.reached_rules, timeout_cycles=256)
        return await self.consume('new_source_after_highest_provider_failure', lambda token:
            main_counter(token) == 3 and steady_history(token, CONDITIONAL))

    async def steer_learning(self, source, goal, checks):
        if goal not in (0, 3):
            raise ValueError('choose a semantic Main direction endpoint')
        source = await self.query(source)
        for _ in range(4):
            counter = main_counter(self.checker.source_token(source))
            if counter == goal:
                await self.restart(source)
                return await self.consume('owned_live_learning_direction_endpoint', lambda token:
                    main_counter(token) == goal and steady_history(token, CONDITIONAL if goal else FALLBACK))
            taken = counter < goal
            accepted = await self.resolve(source, BpuBranchFeedback(CONDITIONAL, self.pc, 1,
                taken=int(taken), mispredict=int((counter >= 2) != taken)), retire=False)
            checks.resolved(source, accepted)
            source = await self.query(source)
        raise AssertionError('normal owned outcomes did not reach Main direction endpoint')

    async def negative_consumer_after_aging(self, source, checks):
        prepared = await self.steer_main(source, 0)
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(prepared)
        seed = checks.history_seeds[False][2]
        def original_negative(token):
            value = provider(self.checker.model.sources, token)
            return (steady_history(token, FALLBACK) and value is not None
                    and (value.key, value.tag, value.position) == (seed.key, seed.tag, seed.position)
                    and value.counter < 4)
        return await self.consume('original_negative_history_consumed_after_global_maintenance', original_negative)


@asynccontextmanager
async def early_aging_program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=EarlyAgingProgram) as env:
        diagnostics = EarlyAgingDiagnostics(agent)
        diagnostics.start()
        try:
            yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage)
            raise
        finally:
            await diagnostics.aclose()
