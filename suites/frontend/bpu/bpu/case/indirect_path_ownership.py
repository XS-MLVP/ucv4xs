"""Instruction outcomes and semantic milestones; no raw signal driving."""
from suites.frontend.bpu.bpu.checker.indirect_path_ownership import Checks
from suites.frontend.bpu.bpu.env.indirect_path_ownership import experiment
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.pipeline import Outcome
from suites.frontend.bpu.tage.model.semantic import HISTORIES


async def run_program(env):
    checks = env.checks
    anchor = await env.initialize()
    await env.resolve_owned('predecessor', anchor)
    await env.resolve_owned('conditional', await env.query_successor(anchor))
    anchor = await env.seed_early(anchor)
    await env.controls(early=False)
    for phase in ('not-taken', 'strengthen-negative', 'fallback'):
        await env.resolve_owned(phase, await env.query_successor(anchor))
    anchor = await env.stable_predecessor(anchor)
    for phase in ('stable-target-cold', 'stable-target-reinforce', 'stable-target-confirm'):
        await env.resolve_owned(phase, await env.query_successor(anchor))
    checks.target_consumer(await env.query_successor(anchor))
    await env.controls(target=False)
    await env.resolve_owned('different-main-target', await env.query_successor(anchor))
    await env.controls(target=True)
    await env.controls(early=True)
    accepted = checks.open()
    await RecoveryDriver(env.agent, env.checker).send(anchor,
        position=checks.program.recovery_offset, branch_type=int(Kind.DIRECT), target=checks.program.b,
        until=None if checks.program.flowing else accepted)
    await env.observation.wait('candidate_original_S1_accepted', lambda _: accepted.done(), timeout_cycles=256)
    await env.observation.wait('candidate_original_target_repair', lambda _: checks.repair is not None)
    teacher = await env.agent.next_transaction(start_pc=checks.program.b, after_tick=checks.selected_tick - 1)
    env.checks.save(teacher)
    await env.pause()
    await env.observation.wait('candidate_actual_original_short_learning', lambda _: checks.confirmed is not None)
    await env.agent.set_ready(prediction=True, meta=True)
    await env.observation.wait('passive_restored_and_new_direction_originals',
        lambda _: checks.new_a is not None and checks.new_b is not None, timeout_cycles=256)
    for pc, record in ((checks.program.a, checks.new_a), (checks.program.b, checks.new_b)):
        token = env.checker.source_receipts[record['tick']]
        source = await env.agent.next_transaction(start_pc=pc, after_tick=env.checker.s1_accepts[token.sequence] - 1)
        env.checks.check(token.sequence, env.checks.save(source).sequence, 'complete actual receipt matches passive original')
    await env.pause()
    checks.finish()
    return checks.facts


async def run(agent, profile, coverage, evidence):
    checks = Checks(profile, coverage=coverage)
    try:
        async with experiment(agent, checks) as env:
            evidence.update(await run_program(env))
            state = env.checker.board.status
            evidence['comparison_status'] = {name: getattr(state, name) for name in
                ('checked', 'passed', 'failed', 'pending', 'processing')}
    finally:
        if hasattr(checks, 'failure_evidence') and checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure_context'] = checks.failure_evidence()
