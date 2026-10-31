from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""Owned recovery paths and a monitor-terminated short-provider issue window."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.env.early_protection import EarlyProtectionProgram
from suites.frontend.bpu.bpu.env.early_direction import early_direction_program
from suites.frontend.bpu.bpu.model.early_opposition import resident
from suites.frontend.bpu.bpu.model.early_short_protection import OLDER_PATHS
from suites.frontend.bpu.bpu.monitor.early_aging import EarlyAgingDiagnostics


class EarlyShortProtectionProgram(EarlyProtectionProgram):
    recovery_position = FALLBACK

    async def restart(self, source):
        await self.pause()
        return await self.recovery.send(source, position=self.recovery_position,
                                        branch_type=1 if self.recovery_position == 2 else 2)

    async def _history_consumer(self, source, older, *, longer=False):
        checks = self.checker.coverage
        await self.settled(checks)
        await self.agent.configure_predictors(abtb=False, settle=True)
        for position in older:
            self.recovery_position = position
            source = await self.query(source)
        self.recovery_position = FALLBACK
        source = await self.query(source)
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.settled(checks)
        accepted = checks.open_original(longer=longer)
        await self.recovery.send(source, position=FALLBACK, branch_type=2, until=accepted)
        source = await self.agent.next_transaction(start_pc=self.pc, after_tick=checks.selected_tick-1)
        checks.window_receipt(source)
        self.owners.append(source)
        await self.settled(checks)
        return source

    async def original_short(self, source, older=OLDER_PATHS[0]):
        return await self._history_consumer(source, older)

    async def allocated_long_consumer(self, source):
        return await self._history_consumer(source, OLDER_PATHS[1], longer=True)

    async def positive(self, source):
        checks = self.checker.coverage
        await self.settled(checks)
        before = resident(self.checker.model.sources, checks.identity.key), checks.ledger.protection
        source = await self.steer_main(source, 3)
        source = await self.positive_base(source, checks.identity.key)
        checks.preserved_other_history(source, before)
        return source


@asynccontextmanager
async def early_short_protection_program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=EarlyShortProtectionProgram) as env:
        diagnostics = EarlyAgingDiagnostics(agent)
        diagnostics.start()
        try:
            yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage)
            raise
        finally:
            await diagnostics.aclose()
