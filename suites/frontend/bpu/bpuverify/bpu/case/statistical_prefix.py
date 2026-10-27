"""Real instruction outcomes, shared SC experience and exact prefix effects."""
from bpuverify.bpu.checker.statistical_prefix import Checks
from bpuverify.bpu.env.statistical_prefix import experiment
from bpuverify.bpu.model.conditional_prefix import target_state
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.tage.model.semantic import TABLES


async def prepare_branch(env, pc, *, target_branch):
    c, p = env.checks, env.checks.program
    await env.controls(tage=False)
    if target_branch:
        await env.feedback(await env.query(pc), Outcome(4, p.a, Kind.INDIRECT, True, mispredict=True))
        for _ in range(2):
            await env.feedback(await env.query(pc), Outcome(4, p.a, Kind.INDIRECT, True))
    await env.conditional(await env.query(pc), True)
    await env.conditional(await env.query(pc), False)
    if not p.positive:
        await env.conditional(await env.query(pc), True)
    await env.controls(tage=True)
    await env.conditional(await env.query(pc), p.positive, maximum=True)
    if target_branch:
        await env.controls(tage=False)
        await env.conditional(await env.query(pc), not p.positive)
        await env.controls(tage=True)
    source = await env.query(pc)
    token = c.save(source)
    fields = dict(c.bank.tage_snapshot(token, resolved=True).wanted)
    main = token.lookup.values()
    slot, = [slot for slot in range(10) if main.get(f'{slot}.valid') and main[f'{slot}.position'] == 2]
    c.check((TABLES - 1, 4 if p.positive else 3),
        (fields[f'{slot}.table'], fields[f'{slot}.counter']), 'real weak highest-history provider')
    direction = fields[f'{slot}.taken'] if fields[f'{slot}.valid'] else main[f'{slot}.taken']
    c.check(not p.positive if target_branch else p.positive, bool(direction), 'retained TAGE/base final direction')


async def prepare_sources(env,*,teaching_count=None):
    c, p = env.checks, env.checks.program
    await prepare_branch(env, p.b, target_branch=True)
    await prepare_branch(env, p.x, target_branch=False)
    await env.controls(sc=True)
    control = await env.query(p.b)
    original = c.bank.statistical_snapshot(c.save(control), resolved=True)
    c.check((0, 0, 0, 0), original.prediction.used, 'cold SC has insufficient evidence and cannot select a direction')
    c.mark('unused-SC-control')
    c.mark('original-history-and-SC-read')
    minimum = 3 if p.positive else 4
    count = minimum if teaching_count is None else teaching_count
    if type(count) is not int or count<minimum:
        raise ValueError('declared sufficient independent teaching originals required')
    teaching = tuple([await env.query(p.x) for _ in range(count)])
    for receipt in teaching:
        value = c.bank.statistical_snapshot(c.save(receipt), resolved=True)
        c.check(original.prediction.read.indices, value.prediction.read.indices, 'different instruction identities share SC features')
        c.check(False, value.original.history.common_valid, 'invalid recovery history does not train global/backward families')
        await env.conditional(receipt, p.positive)
    c.check(len(teaching), len({c.save(receipt).sequence for receipt in teaching}), 'every teaching feedback has a distinct real original')
    c.mark('distinct-real-teaching-originals')
    source = await env.query(p.b)
    token = c.save(source)
    value = c.bank.statistical_snapshot(token, resolved=True)
    fields = dict(c.bank.tage_snapshot(token, resolved=True).wanted)
    slot, = [slot for slot in range(10) if fields.get(f'{slot}.has_provider')]
    c.check(4 if p.positive else 3, fields[f'{slot}.counter'], 'SC teaching did not train the target TAGE identity')
    c.check((1,int(p.positive)),(value.prediction.used[slot],value.prediction.directions[slot]),
        'SC independently earns direction authority')
    if teaching_count is None:
        # Preserve the old fixed program's additional regression control.
        # Extended teaching changes bias subfeatures; its exact signed sum
        # belongs to ScReference and is compared by the pipeline checker.
        c.check(23 if p.positive else -19,value.prediction.sums[slot],'original SC calibration score')
    main = token.lookup.values()
    direction = fields[f'{slot}.taken'] if fields[f'{slot}.valid'] else main[f'{slot}.taken']
    c.check(not p.positive, bool(direction), 'SC direction really opposes final TAGE choice')
    c.mark('SC-opposes-retained-TAGE-choice')
    c.check((2 if p.positive else 4, p.d if p.positive else p.a,
        'main' if p.positive else 'indirect-history'),
        (value.late.branch.position, value.late.branch.target, value.late.source), 'only the selected execution prefix owns the complete target')
    c.mark('executed-prefix-selects-complete-target')
    return source


async def run_program(env):
    source = await prepare_sources(env)
    c, p = env.checks, env.checks.program
    value = c.bank.statistical_snapshot(c.save(source), resolved=True)
    slot, = [i for i,used in enumerate(value.prediction.used) if used]
    if p.positive:
        c.guard = target_state(c.bank)
    resolution = await env.conditional(source, p.positive)
    if p.positive:
        c.check(None, c.bank.targets.feedback_for(resolution), 'unexecuted indirect is absent, not a fabricated not-taken outcome')
        c.check(True, c.guard_cycles > 0, 'actual no-learning guard surrounds the accepted prefix')
        c.guard = None
    else:
        c.check(True, c.bank.targets.feedback_for(resolution) is not None, 'actually executed indirect owns legitimate feedback')
    c.mark('actual-correct-prefix-feedback')
    fresh = await env.query(p.b)
    late = c.bank.statistical_snapshot(c.save(fresh), resolved=True).late
    c.check(value.late, late, 'a fresh independently checked consumer follows the learned execution prefix')
    c.check(True, c.updates >= (3 if p.positive else 4) * 3, 'all intended signed weight patches were actually compared')
    c.mark('fresh-consumer-after-learning')
    result = c.finish(fresh)
    result.update(SC_sum=value.prediction.sums[slot], target=value.late.branch.target,
        SC_original_read_is_independent=True, no_bank_sweep=True)
    return result


async def run(agent, profile, coverage, evidence):
    checks = Checks(profile, coverage)
    try:
        async with experiment(agent, checks) as env:
            evidence.update(await run_program(env))
    finally:
        if checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure'] = dict(tick=checks.pipeline.last_tick,
                error=str(checks.pipeline.failure), accepted_feedbacks=len(checks.feedbacks))


async def run_context_program(env):
    c,p=env.checks,env.checks.program
    await env.controls(abtb=False,ittage=False)
    for pc,position,target,kind in ((p.prefix,2,p.prefix_target,Kind.CONDITIONAL),
            (p.jump,0,p.b,Kind.DIRECT)):
        await env.feedback(await env.query(pc),Outcome(position,target,kind,True,mispredict=True))
    await env.conditional(await env.query(p.b),True)
    await env.controls(tage=True)
    await env.conditional(await env.query(p.b),False,maximum=True)
    for _ in range(2 if p.agrees else 1):
        await env.conditional(await env.query(p.b),p.agrees)
    await env.controls(sc=True)
    control=await env.query(p.b)
    slot,cold=c.provider(control)
    c.check(False,bool(cold.prediction.used[slot]),'cold SC cannot claim direction authority')
    c.context_read=cold.original.read
    c.mark('cold-unused-control')
    # Four distinct cold originals supply sufficient five-family evidence at
    # the reset-derived threshold. This is instruction experience, not a
    # cycle delay; each acceptance and full effect is independently checked.
    c.originals=tuple([await env.query(p.b) for _ in range(4)])
    for index,source in enumerate(c.originals):
        c.context_source(source)
        await env.context_feedback(source,True,f'teaching-{index}')
    used=await env.query(p.b)
    slot,value=c.provider(used)
    c.check((1,1,1),(value.prediction.used[slot],value.prediction.directions[slot],
        value.prediction.above[slot]),'genuine five-family experience earns sufficiently confident SC authority')
    c.check(p.agrees,value.prediction.branches[slot].tage_counter>=4,
        'declared raw TAGE agreement belongs to the original provider')
    c.check(True,all(a!=b for a,b in zip(cold.original.read.weights,value.original.read.weights,strict=True)),
        'fresh consumer independently reads changed experience in all five families')
    c.mark('fresh-used-consumer')
    await env.context_feedback(used,True,'used-correct')
    after_correct=await env.query(p.b)
    _,correct=c.provider(after_correct)
    c.check(value.original.read.weights,correct.original.read.weights,'correct feedback consumer keeps all weights')
    await env.context_feedback(after_correct,False,'used-wrong')
    after_wrong=await env.query(p.b)
    _,wrong=c.provider(after_wrong)
    c.check(True,all(a!=b for a,b in zip(correct.original.read.weights,wrong.original.read.weights,strict=True)),
        'fresh consumer sees the wrong original learned in every family')
    await env.probe_invalid_history(after_wrong)
    return used,after_correct,after_wrong


async def run_context(agent,profile,coverage,evidence):
    from bpuverify.bpu.checker.statistical_prefix import ContextChecks
    from bpuverify.bpu.env.statistical_prefix import ContextProgram
    checks=ContextChecks(profile,coverage)
    try:
        async with experiment(agent,checks,program_type=ContextProgram) as env:
            consumers=await run_context_program(env)
        # Scope teardown and the independent PHR checker must also pass.
        evidence.update(checks.finish_context(consumers))
    except Exception as error:
        evidence['error']=str(error)
        raise
    finally:
        evidence.setdefault('invalid_history_masking',checks.invalid_history.witnesses)
        evidence.setdefault('cancelled_warm_query',checks.invalid_history_probe)
        if checks.pipeline is not None:
            evidence.setdefault('receipts',checks.receipts)
            if checks.pipeline.failure is not None:
                evidence['first_failure']=dict(tick=checks.pipeline.last_tick,
                    error=str(checks.pipeline.failure),accepted_feedbacks=len(checks.feedbacks))


async def run_concurrent_context(agent,profile,coverage,evidence):
    from bpuverify.bpu.checker.statistical_prefix import ConcurrentContextChecks
    from bpuverify.bpu.env.statistical_prefix import ConcurrentContextProgram
    checks=ConcurrentContextChecks(profile,coverage)
    try:
        async with experiment(agent,checks,program_type=ConcurrentContextProgram) as env:
            await env.controls(ubtb=True,abtb=False,ittage=False)
            await env.feedback(await env.query(checks.program.loop),
                Outcome(4,checks.program.loop,Kind.DIRECT,True,mispredict=True))
            await env.controls(ubtb=False)
            consumers=await run_context_program(env)
        evidence.update(checks.finish_context(consumers))
    except Exception as error:
        evidence['error']=str(error)
        raise
    finally:
        evidence.setdefault('invalid_history_masking',checks.invalid_history.witnesses)
        evidence.setdefault('cancelled_warm_query',checks.invalid_history_probe)
        evidence.setdefault('concurrent_original_feedback',checks.arbitrations)
        if checks.arbitration is not None:
            evidence['unfinished_feedback']={key:value for key,value in checks.arbitration.items() if key!='payload'}
        if checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure']=dict(tick=checks.pipeline.last_tick,error=str(checks.pipeline.failure),
                accepted_feedbacks=len(checks.feedbacks))
