"""One genuine Main learning and fresh consumer, under two cold controls."""
from bpuverify.bpu.env.ahead_working_set import ahead_working_set_env
from bpuverify.bpu.model.cold_source_isolation import RULES
from bpuverify.bpu.transaction.types import BpuBranchFeedback


async def check_cold_source_isolation(agent, program, coverage):
    disabled = program.source if program.mode == 'disabled-from-reset' else None
    async with ahead_working_set_env(agent, program, coverage, disabled_from_reset=disabled) as env:
        source = env.source
        edge, = program.edges(0)
        coverage.record('reached','original-main-discovery',source_tick=source.meta_tick)
        result = await env.resolve(source, BpuBranchFeedback(edge.position, edge.target, edge.kind,
            taken=1,mispredict=1),retire=False)
        env.checks.accepted(source,result,edge)
        coverage.record('reached','actual-feedback-owned',accepted_tick=result[0])
        consumer = await env.recover(source,edge)
        token = env.checker.source_token(consumer)
        env.checks.check(True, token.middle is not None and token.middle.branch.taken
            and token.middle.branch.target == edge.target and int(token.middle.branch.kind) == 1,
            'fresh active Main consumer survives disabled unused source')
        coverage.record('reached','fresh-main-consumer',source_tick=consumer.meta_tick)
        original, resolve, redirect = env.checks.originals[0]
        env.checks.check((resolve,redirect),(original.meta.resolve,original.meta.redirect),
                         'cold launch does not mutate the original source')
        coverage.record('reached','immutable-original-source',source_tick=source.meta_tick)
        env.checks.check(set(RULES),coverage.reached,'all cold isolation obligations actually reached')
        for rule in RULES:coverage.record('checked',rule)
