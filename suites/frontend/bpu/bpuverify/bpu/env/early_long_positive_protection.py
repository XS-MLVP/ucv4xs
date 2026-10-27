"""Normal historical ancestors make the same original long record reachable."""
from contextlib import asynccontextmanager

from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.env.early_positive_protection import EarlyPositiveProtectionProgram
from bpuverify.bpu.model.early_long_positive_protection import REVISIT_PREFIX, SHORT_REVISIT_PREFIX
from bpuverify.bpu.monitor.early_aging import EarlyAgingDiagnostics


class EarlyLongPositiveProtectionProgram(EarlyPositiveProtectionProgram):
    async def companion_short(self, source, *, preserve=False):
        checks = self.checker.coverage
        return await self._source_window(source, older=SHORT_REVISIT_PREFIX,
                                         open_window=lambda: checks.open_short(preserve=preserve))

    async def original_long(self, source, *, penalty=False, expect_taken=None):
        return await self._source_window(source, older=REVISIT_PREFIX if penalty else None,
                                         recovery_position=2 if penalty else 4, expect_taken=expect_taken)


@asynccontextmanager
async def early_long_positive_protection_program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=EarlyLongPositiveProtectionProgram) as env:
        diagnostics = EarlyAgingDiagnostics(agent); diagnostics.start()
        try:
            yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage)
            raise
        finally:
            await diagnostics.aclose()
