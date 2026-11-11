"""Explicit program geometry on the existing source-owned recursion lifetime."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.ras.layered_recursion import check_with_agent as check_lifetime
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import ROOT
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import ROOT_RETURN
from suites.frontend.bpu.testbenches.bpu.model.ras.adjacent_recursion import POSITION


async def check_with_agent(agent,program,coverage,evidence):
    await check_lifetime(agent,program,coverage,evidence,root_pc=ROOT,layer_pcs=program.layer_pcs,
        root_return=ROOT_RETURN,position=POSITION)
