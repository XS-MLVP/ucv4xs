"""Real Main/Ahead preparation and existing monitor-terminated source windows."""
from contextlib import asynccontextmanager
from bpuverify.bpu.env.early_positive_protection import EarlyPositiveProtectionProgram
from bpuverify.bpu.env.early_direction import early_direction_program
from bpuverify.bpu.case.early_opposition import exercise_negative_opposition
from bpuverify.bpu.monitor.early_aging import EarlyAgingDiagnostics


class Program(EarlyPositiveProtectionProgram):
    async def prepare(self):
        checks = self.checker.coverage
        source = await exercise_negative_opposition(self, checks)
        checks.protect_seed()
        source = await self.negative_base(source); checks.negative_base_source(source)
        source = await self.steer_main(source, 3); checks.main_positive(source); checks.arm_seed()
        source = await self.base_bias(source, taken=True); checks.seed_ready()
        return source

    async def edge(self, source, name, *, taken, older=None):
        checks = self.checker.coverage
        await self.settled(checks); checks.arm(name)
        source = await self._source_window(source, older=older, expect_taken=taken)
        await self.wait_edge(checks, name); checks.owned_edge(name, source)
        return source

    async def consume_final(self, source):
        checks = self.checker.coverage
        source = await self.steer_main(source, 3)
        source = await self.original_taken(source)
        checks.fresh_consumer(source); await self.settled(checks)
        return source


@asynccontextmanager
async def program(agent, checks):
    async with early_direction_program(agent, checks.pc, checks, program_type=Program) as env:
        diagnostics = EarlyAgingDiagnostics(agent); diagnostics.start()
        try: yield env
        except Exception as error:
            diagnostics.annotate(error, checks.lineage); raise
        finally: await diagnostics.aclose()
