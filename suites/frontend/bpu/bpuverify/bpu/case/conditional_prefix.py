"""Instruction outcomes and semantic milestones; no raw signal driving."""
from bpuverify.bpu.checker.conditional_prefix import Checks
from bpuverify.bpu.env.conditional_prefix import experiment
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.tage.model.semantic import HISTORIES


async def prepare_sources(env):
    """Real conditional loop, retained indirect target and weak negative TAGE."""
    c, p = env.checks, env.checks.program
    anchor = await env.initialize()
    await env.feedback('discover-A4-B', anchor, Outcome(4, p.b, Kind.DIRECT, True, mispredict=True))
    await env.feedback('discover-B4-A', await env.query_owned(anchor), Outcome(4, p.a, Kind.INDIRECT, True, mispredict=True))
    await env.conditional('discover-B2-D', await env.query_owned(anchor))
    await env.from_predecessor(anchor)
    return_source = await env.source(p.d, name='real_D4_return_source')
    await env.feedback('discover-D4-A', return_source, Outcome(4, p.a, Kind.DIRECT, True, mispredict=True))
    await env.query_owned(anchor)
    await env.from_predecessor(anchor)
    c.seed = await env.source(p.b, lambda t: t.early.source in ('ahead', 'ahead-direction')
        and t.early.branch.position == 2 and t.early.branch.target == p.d, name='real_early_conditional_D')
    c.save(c.seed)
    anchor = await env.source(p.a, lambda t: t.early.source == 'ahead' and t.early.branch.position == 4,
        name='new_A4_after_real_early_conditional')
    await env.from_predecessor(anchor)
    anchor = await env.source(p.a, lambda t: t.history.history % (1 << max(HISTORIES)) == p.recent,
        name='stable_real_A_B_D_A_history')
    c.stable = anchor
    c.save(anchor)
    await env.controls(abtb=False, tage=False, ittage=False)
    for n in range(2):
        source = await env.query_owned(anchor)
        late = c.bank.target_snapshot(env.checker.source_token(source), resolved=True).late
        await env.conditional(f'base-negative-{n}', source, taken=False,
            wrong=late.branch.kind == Kind.CONDITIONAL, indirect=True)
    await env.conditional('first-Main-target-C', await env.query_owned(anchor), taken=False,
        wrong=False, indirect=True, indirect_target=p.c, indirect_wrong=True)
    await env.controls(ittage=True)
    for n in range(3):
        await env.conditional(f'real-indirect-target-A-{n}', await env.query_owned(anchor), taken=False,
            wrong=False, indirect=True, indirect_wrong=n == 0)
    c.target_control = await env.query_owned(anchor)
    prediction = c.bank.target_snapshot(env.checker.source_token(c.target_control), resolved=True).prediction
    c.check(True, prediction.provider is not None, 'real independent target provider prepared')
    c.check((p.a, 3), (prediction.target // 2, prediction.confidence), 'independent A target fully learned')
    await env.controls(ittage=False)
    await env.conditional('retain-A-while-Main-learns-C', await env.query_owned(anchor), taken=False,
        wrong=False, indirect=True, indirect_target=p.c, indirect_wrong=True)
    await env.controls(ittage=True)
    for n in range(2): await env.conditional(f'restore-base-positive-{n}', await env.query_owned(anchor))
    await env.controls(tage=True)
    await env.conditional('maximum-history-negative-provider', await env.query_owned(anchor), taken=False,
        wrong=True, indirect=True, maximum=True)
    await env.conditional('strengthen-negative-provider', await env.query_owned(anchor), taken=False, wrong=False, indirect=True)
    await env.controls(tage=False)
    return anchor


async def run_program(env):
    c, p = env.checks, env.checks.program
    anchor = await prepare_sources(env)
    await env.conditional('base-near-positive', await env.query_owned(anchor))
    await env.controls(tage=True)
    for n in range(3 if p.strong else 1):
        await env.conditional(f'qualified-conditional-direction-{n}', await env.query_owned(anchor), wrong=n == 0)
    await env.controls(abtb=True)
    accepted = c.open()
    await RecoveryDriver(env.agent, env.checker).send(anchor, position=p.recovery_offset,
        branch_type=int(Kind.DIRECT), target=p.b, until=None if p.flowing else accepted)
    await env.observation.wait('exact_original_early_conditional_accepted', lambda _: accepted.done(), timeout_cycles=256)
    await env.observation.wait('exact_original_final_conditional', lambda _: c.final is not None)
    source = await env.agent.next_transaction(start_pc=p.b, after_tick=c.selected_tick - 1)
    c.check(c.winner.sequence, c.save(source).sequence, 'full actual winning original receipt')
    await env.pause()
    await env.conditional('guarded-conditional-only', source, wrong=False)
    c.close_guard()
    for n in range(8):
        fresh = await env.query_owned(anchor)
        late = c.bank.target_snapshot(env.checker.source_token(fresh), resolved=True).late
        if late.branch.kind == Kind.INDIRECT: break
        await env.conditional(f'legitimate-later-indirect-{n}', fresh, taken=False, wrong=True, indirect=True)
    else: raise AssertionError('legitimate direction feedback did not produce an indirect consumer within counter capacity')
    await env.pause()
    # AheadBTB cleanup writes are buffered behind single-port reads.  A real
    # quiet window must retire them; only then may the reference require the
    # duplicate copy to be gone.  Continuous-read visibility is handled by the
    # bounded content-identical allowance recorded by the checker.
    allowance_cycles = env.checker.counts['abtb-buffered-duplicate-cycles']
    duplicate = env.checker.duplicate_allowances[-1] if env.checker.duplicate_allowances else None
    drain_from = env.checker.last_tick
    await env.drain_bank_writes()
    drained = await env.source(p.a, name='post_drain_ahead_duplicate_cleanup')
    c.save(drained)
    c.check(allowance_cycles, env.checker.counts['abtb-buffered-duplicate-cycles'],
        'read-free window retires the buffered AheadBTB duplicate cleanup')
    if duplicate is not None:
        watched = (duplicate['bank'], duplicate['row'], duplicate['way'])
        later = [entry for entry in env.checker.duplicate_history.get(watched, ())
                 if entry['tick'] > drain_from]
        c.check(True, bool(later), 'post-drain read reaches the duplicate AheadBTB row')
        c.check({0}, {entry['actual'] for entry in later},
            'post-drain read no longer reports the stale duplicate copy')
    result = c.finish(fresh)
    result['duplicate_visibility'] = dict(
        watched_cycles=env.checker.counts['cycles'],
        allowed_cycles=allowance_cycles,
        allowed_ways=env.checker.counts['abtb-buffered-duplicate-ways'],
        after_drain_allowed_cycles=env.checker.counts['abtb-buffered-duplicate-cycles'],
        records=list(env.checker.duplicate_allowances),
        history={str(key): list(value) for key, value in env.checker.duplicate_history.items()})
    return result


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
