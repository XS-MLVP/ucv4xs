"""Reuse public driver/monitor orchestration with long-provider semantics."""
from suites.frontend.bpu.utage.env.selective_protection import run as run_protection
from suites.frontend.bpu.utage.checker.long_protection import Checks
from suites.frontend.bpu.utage.monitor.long_protection import Monitor


async def run(agent,program,coverage,evidence):
    await run_protection(agent,program,coverage,evidence,checks_type=Checks,monitor_type=Monitor)
