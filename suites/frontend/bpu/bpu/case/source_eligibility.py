"""Environment eligibility scenarios; the environment owns timing and I/O."""
from suites.frontend.bpu.bpu.env.source_eligibility import run as _run


async def run(agent,program,evidence):
    await _run(agent,program,evidence)
