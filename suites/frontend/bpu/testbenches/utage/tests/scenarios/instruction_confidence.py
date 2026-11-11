"""A domain-level confidence handover; no pin, edge or waiting mechanics."""
from suites.frontend.bpu.testbenches.utage.tests.scenarios.lifetimes.instruction_confidence import run


async def check_instruction_confidence(agent,program,coverage,evidence):
    await run(agent,program,coverage,evidence)
