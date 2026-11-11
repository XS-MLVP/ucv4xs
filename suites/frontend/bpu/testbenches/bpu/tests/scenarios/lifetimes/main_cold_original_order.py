"""Preserve the original cold window across later, younger learning."""
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_service import branch
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.main_original_lifetime import run_original_lifetime
from suites.frontend.bpu.testbenches.bpu.checker.main_cold_original_order import Checks
from suites.frontend.bpu.testbenches.bpu.model.main_sources import source_entries
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import PC
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import STREAM_PC
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import EARLIER
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import LATER
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import INITIAL_TARGET
from suites.frontend.bpu.testbenches.bpu.model.main_original_order import LATER_TARGET


async def prepare(env,helper,p):
    await env.teach(helper,branch(12,STREAM_PC,2,wrong=True))
    cold=await env.capture_source(PC)
    original=env.checker.source_token(cold)
    assert not any(s.hit for row in source_entries(original.lookup) for s in row)
    # From this point the anchor only advances. No older helper redirect can
    # discard the pending cold occurrence; no software commit is invented.
    source=await env.capture_source(PC+EARLIER+1)
    await env.teach(source,branch(LATER,LATER_TARGET,1,wrong=True))
    for _ in range(2-p.sibling_counter):
        source=await env.capture_source(PC+EARLIER+1)
        token=env.checker.source_token(source)
        await env.teach(source,branch(LATER,LATER_TARGET,1,taken=False,wrong=bool(token.middle.branch.taken)))
    source=await env.capture_source(PC)
    await env.teach(source,branch(EARLIER,INITIAL_TARGET,3,wrong=True))
    current=await env.capture_source(PC)
    env.checker.windows.ledger.live(env.checker.receipt_window(cold))
    return cold,current


async def run(agent,program,coverage,evidence):
    await run_original_lifetime(agent,program,coverage,evidence,prepare_sources=prepare,checker_factory=Checks)
