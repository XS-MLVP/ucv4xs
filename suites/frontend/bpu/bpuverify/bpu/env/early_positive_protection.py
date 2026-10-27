from bpuverify.bpu.model.early_opposition import FALLBACK
"""Normal base histories and exact original-T/allocated-NT source windows."""
from contextlib import asynccontextmanager

from bpuverify.bpu.env.early_protection import EarlyProtectionProgram
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.model.early_opposition import resident, ahead_owner, main_counter, steady_history
from bpuverify.bpu.model.early_positive_protection import OLDER_PATHS
from bpuverify.bpu.monitor.early_aging import EarlyAgingDiagnostics


class EarlyPositiveProtectionProgram(EarlyProtectionProgram):
    async def negative_base(self, source):
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.restart(source)
        return await self.consume('owned_negative_base_history', lambda token:
            steady_history(token, FALLBACK) and (owner := ahead_owner(self.checker.model.sources, token)) is not None
            and owner[1] == 0)

    async def base_bias(self, source, *, taken):
        checks = self.checker.coverage
        await self.settled(checks)
        before = resident(self.checker.model.sources, checks.identity.key), checks.ledger.protection
        if not taken:
            source = await self.steer_main(source, 0)
        await self.agent.configure_predictors(abtb=True, settle=True)
        # Deliberately keep the already stable history; inserting a recovery
        # here would consume a transient original-T record while biasing base.
        await self.agent.set_ready(prediction=True, meta=True)
        source = await self.consume('base_only_'+('taken' if taken else 'not_taken'), lambda token:
            main_counter(token) == (3 if taken else 0) and steady_history(token, 2 if taken else FALLBACK)
            and (owner := ahead_owner(self.checker.model.sources, token)) is not None
            and owner[1] == (3 if taken else 0))
        checks.preserved_base_bias(source, before, taken)
        await self.settled(checks)
        return source

    async def _source_window(self, source, *, older=None, longer=False, expect_taken=None,
                             recovery_position=FALLBACK, open_window=None):
        checks = self.checker.coverage
        await self.settled(checks)
        if older is not None:
            await self.agent.configure_predictors(abtb=False, settle=True)
            for position in older:
                await self.settled(checks)
                boundary = await self.recovery.send(source, position=position, branch_type=1 if position == 2 else 2)
                source = await self.agent.next_transaction(start_pc=self.pc, after_tick=boundary)
                checks.remember(source); self.owners.append(source)
        # The last history query is still flowing. Drain it with fast learning
        # disabled before enabling the new bounded original-source window.
        await self.settled(checks)
        await self.agent.configure_predictors(abtb=True, settle=True)
        await self.settled(checks)
        accepted = (checks.open_original(longer=longer, expect_taken=expect_taken)
                    if open_window is None else open_window())
        await self.recovery.send(source, position=recovery_position,
                                 branch_type=1 if recovery_position == 2 else 2, until=accepted)
        source = await self.agent.next_transaction(start_pc=self.pc, after_tick=checks.selected_tick-1)
        checks.window_receipt(source); self.owners.append(source)
        await self.settled(checks)
        return source

    async def original_taken(self, source, *, older=None):
        return await self._source_window(source, older=older)

    async def allocated_not_taken(self, source):
        return await self._source_window(source, older=OLDER_PATHS[1], longer=True)

    async def restore_taken_direction(self, source):
        return await self._source_window(source, expect_taken=False)


@asynccontextmanager
async def early_positive_protection_program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=EarlyPositiveProtectionProgram) as env:
        diagnostics = EarlyAgingDiagnostics(agent); diagnostics.start()
        try:
            yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage)
            raise
        finally:
            await diagnostics.aclose()
