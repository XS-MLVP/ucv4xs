"""Source-qualified boundary programs; existing drivers hide all clock phases."""
from contextlib import asynccontextmanager

from bpuverify.bpu.env.early_opposition import EarlyOppositionProgram
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.model.early_opposition import provider, resident, steady_history, main_counter
from bpuverify.bpu.model.path_history import SHIFT
from bpuverify.utage.model.semantic import HISTORIES
from bpuverify.bpu.monitor.early_aging import EarlyAgingDiagnostics
from bpuverify.bpu.driver.recovery import RecoveryDriver


class EarlyProtectionProgram(EarlyOppositionProgram):
    def __init__(self, *args):
        super().__init__(*args)
        self.recovery = RecoveryDriver(self.agent, self.checker)

    async def query(self, source):
        self.checker.coverage.remember(source)
        result = await super().query(source)
        self.checker.coverage.remember(result)
        return result

    async def consume(self, name, predicate):
        result = await super().consume(name, predicate)
        self.checker.coverage.remember(result)
        return result

    async def restart(self, source):
        await self.pause()
        return await self.recovery.send(source)

    async def settled(self, checks):
        await self.pause()
        await self.observation.wait('all_original_guidance_compared', lambda _: checks.pending is None
            and self.checker.model.sources.short.offered is None and self.checker.model.sources.short.learning is None)

    async def wait_edge(self, checks, edge):
        await self.observation.wait('actual_original_protection_'+edge, lambda _: edge in checks.confirmed,
                                    timeout_cycles=256)

    async def opposed_again(self, source, checks):
        await self.settled(checks)
        sources = self.checker.model.sources
        before = resident(sources, checks.identity.key), checks.ledger.protection
        positive = await self.steer_main(source, 3)
        positive = await self.positive_base(positive, checks.identity.key)
        checks.preserved_other_history(positive, before)
        negative = await self.steer_main(positive, 0)
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(negative)
        return await self.consume('same_original_NT_opposed_again', lambda token:
            (value := provider(self.checker.model.sources, token)) is not None
            and value.key == checks.identity.key and value.tag == checks.identity.tag
            and value.counter < 4 and value.base)

    async def wrong_original(self, source, checks, edge):
        await self.settled(checks)
        before = resident(self.checker.model.sources, checks.identity.key), checks.ledger.protection
        source = await self.steer_main(source, 3)
        checks.preserved_other_history(source, before)
        await self.agent.configure_predictors(abtb=False, settle=True)
        for _ in range(max(HISTORIES)//SHIFT + 2):
            source = await self.query(source)
            if steady_history(self.checker.source_token(source), 4):
                break
        else:
            raise AssertionError('new owned recoveries did not establish original NT history')
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(source)
        await self.wait_edge(checks, edge)
        return await self.consume('fresh_T_source_after_original_penalty', lambda token:
            main_counter(token) == 3 and steady_history(token, 2))

    async def correct_original(self, source, checks, *, edge=None):
        source = await self.steer_main(source, 0)
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(source)
        source = await self.consume('same_original_NT_correct_again', lambda token:
            (value := provider(self.checker.model.sources, token)) is not None
            and (value.key, value.tag) == (checks.identity.key, checks.identity.tag) and value.counter < 4)
        if edge is not None:
            await self.wait_edge(checks, edge)
        await self.settled(checks)
        return source

    async def final_consumer(self, source, checks):
        await self.settled(checks)
        await self.restart(source)
        source = await self.consume('fresh_original_record_after_all_boundary_effects', lambda token:
            (value := provider(self.checker.model.sources, token)) is not None
            and (value.key, value.tag, value.position)==
                (checks.identity.key, checks.identity.tag, checks.identity.position) and value.counter < 4)
        checks.fresh_consumer(source)
        await self.settled(checks)
        return source


@asynccontextmanager
async def early_protection_program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=EarlyProtectionProgram) as env:
        diagnostics = EarlyAgingDiagnostics(agent)
        diagnostics.start()
        try:
            yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage)
            raise
        finally:
            await diagnostics.aclose()
