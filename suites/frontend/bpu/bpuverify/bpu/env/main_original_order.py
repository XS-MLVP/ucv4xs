"""Current-hit original preparation; shared lifetime owns observation and cleanup."""
from bpuverify.bpu.env.main_service import branch
from bpuverify.bpu.env.main_original_lifetime import run_original_lifetime,open_pressure
from bpuverify.bpu.checker.main_original_order import Checks
from bpuverify.bpu.model.main_original_order import PC,STREAM_PC,EARLIER,LATER,INITIAL_TARGET,LATER_TARGET


async def prepare(env,helper,program):
    async def fresh(pc):
        # A real older redirect discards already-resolved setup occurrences.
        # It frees capacity without inventing backend commits or deleting receipts.
        env.anchor=helper
        return await env.capture_source(pc)
    await env.teach(helper,branch(12,STREAM_PC,2,wrong=True))
    source=await fresh(PC+EARLIER+1)
    await env.teach(source,branch(LATER,LATER_TARGET,1,wrong=True))
    for _ in range(2-program.sibling_counter):
        source=await fresh(PC+EARLIER+1)
        token=env.checker.source_token(source)
        await env.teach(source,branch(LATER,LATER_TARGET,1,taken=False,wrong=bool(token.middle.branch.taken)))
    source=await fresh(PC)
    await env.teach(source,branch(EARLIER,INITIAL_TARGET,3,wrong=True))
    older=await fresh(PC)
    younger=await env.capture_source(PC)
    return older,younger



async def run(agent,program,coverage,evidence):
    await run_original_lifetime(agent,program,coverage,evidence,prepare_sources=prepare,checker_factory=Checks)
