"""Reuse public driver/monitor orchestration with long-provider semantics."""
from suites.frontend.bpu.testbenches.utage.tests.scenarios.lifetimes.selective_protection import run as run_protection
from suites.frontend.bpu.testbenches.utage.checker.long_protection import Checks
from suites.frontend.bpu.testbenches.utage.env.monitor.long_protection import Monitor


async def run(agent,program,coverage,evidence):
    await run_protection(agent,program,coverage,evidence,checks_type=Checks,monitor_type=Monitor)
