"""Normal discoveries and original-source learning from interior instruction entries."""
from suites.frontend.bpu.testbenches.bpu.checker.block_entry_learning import Checks
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.early_direction import discover_negative_path
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.early_direction import early_direction_program


async def run(agent,profile,coverage,evidence):
    checks=Checks(coverage,profile)
    try:
        async with early_direction_program(agent,checks.pc,checks) as env:
            await discover_negative_path(env,checks)
            checks.finish()
    finally: evidence.update(checks.snapshot())
