"""Real prediction continues while an independently qualified old result arrives."""
from bpuverify.bpu.case.statistical_prefix import prepare_sources
from bpuverify.bpu.checker.sc_admission import Checks,BurstChecks,ContextBurstChecks
from bpuverify.bpu.env.sc_admission import Program,main_learning_evidence,ContextBurstProgram
from bpuverify.bpu.env.statistical_prefix import experiment
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.model.selection import Kind


async def prepare_context_burst(env):
    c,p=env.checks,env.checks.program
    await env.controls(ubtb=True,abtb=False,ittage=False)
    await env.feedback(await env.query(p.loop),Outcome(4,p.loop,Kind.DIRECT,True,mispredict=True))
    await env.controls(ubtb=False)
    await env.feedback(await env.query(p.loop_prefix),
        Outcome(2,p.loop_prefix,Kind.CONDITIONAL,True,mispredict=True))
    await env.feedback(await env.query(p.jump),Outcome(0,p.b,Kind.DIRECT,True,mispredict=True))
    for context in p.contexts:
        await env.controls(tage=False)
        for _ in range(3):  # Establish a strong Main direction, not a delay.
            await env.conditional(await env.query_context(context),True)
        await env.controls(tage=True)
        source=await env.query_context(context)
        token=c.save(source)
        fields=dict(c.bank.tage_snapshot(token,resolved=True).wanted)
        slot,=[i for i in range(10) if token.lookup.values().get(f'{i}.valid')
               and token.lookup.values()[f'{i}.position']==p.position]
        if not fields[f'{slot}.has_provider']:
            await env.conditional(source,False,maximum=True)
        for _ in range(8):  # The eight-state direction range bounds setup.
            source=await env.query_context(context)
            fields=dict(c.bank.tage_snapshot(c.save(source),resolved=True).wanted)
            counter=fields[f'{slot}.counter']
            if counter==p.provider_counter:break
            await env.conditional(source,counter<p.provider_counter)
        else:raise AssertionError('real original context did not obtain its declared TAGE experience')
        c.provider(source,context)
    await env.controls(sc=True)
    teachers=[]
    for context in p.teaching_contexts:
        source=await env.query_context(context)
        _,value,slot=c.provider(source,context)
        c.check(0,value.prediction.used[slot],'all teachers are captured before any SC learning')
        teachers.append(source)
    for source in teachers:await env.sc_feedback(source,True)
    originals=[]
    for context in p.capture_contexts:
        source=await env.query_context(context)
        _,value,slot=c.provider(source,context)
        c.check((1,1,1),(value.prediction.used[slot],value.prediction.above[slot],value.prediction.directions[slot]),
            'each old original owns independently learned sufficiently confident positive SC experience')
        c.original_controls.setdefault(context,value)
        originals.append(source)
    for source in originals[:p.weakening_count]:await env.sc_feedback(source,False)
    controls=[]
    for context in p.contexts:
        source=await env.query_context(context)
        _,value,slot=c.provider(source,context)
        c.check((0,0),(value.prediction.used[slot],value.prediction.above[slot]),
            'actual fresh consumer proves current confidence differs from every retained old original')
        c.current_controls[context]=value
        controls.append(dict(context=context,numeric=c.numeric_consumer(source),current_sum=value.prediction.sums[slot]))
    c.prove('original-qualification-not-current')
    return tuple(originals[i] for i in p.arrival_order),controls


async def run_context_burst(agent,profile,coverage,evidence):
    checks=ContextBurstChecks(profile,coverage)
    try:
        async with experiment(agent,checks,program_type=ContextBurstProgram) as env:
            sources,controls=await prepare_context_burst(env)
            await env.controls(tage=False,ubtb=True)
            await env.stream_feedbacks(sources)
            returning=await env.return_from_stream()
            fresh=tuple([await env.query_context(context) for context in checks.program.contexts])
        evidence.update(checks.finish_context_burst(fresh))
        evidence['current_confidence_controls']=controls
        evidence['return_from_stream']=returning
    except Exception as error:
        evidence['error']=str(error)
        raise
    finally:
        evidence.setdefault('accepted_ticks',checks.accepted_ticks)
        evidence.setdefault('actual_patch_offers',checks.patch_offers)


async def prepare_read_only_source(env):
    c,p = env.checks,env.checks.program
    await prepare_sources(env,teaching_count=5 if p.positive else 6)
    # A provider direction change also selects another bias subfeature. The
    # extra real teaching originals preserve enough SC authority after it.
    await env.controls(sc=False)
    await env.conditional(await env.query(p.b),not p.positive)
    await env.controls(sc=True)
    source = await env.query(p.b)
    prediction = c.bank.statistical_snapshot(c.save(source),resolved=True).prediction
    slot, = [i for i,used in enumerate(prediction.used) if used]
    c.check((int(p.positive),not p.positive),(prediction.directions[slot],prediction.branches[slot].tage_counter>=4),
        'real used SC direction differs from the original raw TAGE direction')
    return source


async def run(agent,profile,coverage,evidence):
    checks = Checks(profile,coverage)
    try:
        async with experiment(agent,checks) as original:
            env = Program(agent,original.observation,original.anchor,checks.program.a)
            # A normal MicroBTB-learned self-loop provides a genuine steady
            # early stream; an endlessly corrected Main-only loop does not.
            await env.controls(ubtb=True)
            await env.feedback(await env.query(checks.program.loop),
                Outcome(4,checks.program.loop,Kind.DIRECT,True,mispredict=True))
            # Establish a recent *real* recovery owner before calibration.
            # Reusing the reset checkpoint after an active loop exceeds the
            # physical path-history retention bound, even if Python kept it.
            env.anchor = await env.query(checks.program.a)
            await env.controls(ubtb=False)
            source = await prepare_read_only_source(env) if checks.program.read_only else await prepare_sources(env)
            await env.controls(ubtb=True)
            await env.stream_feedback(source)
            evidence.update(checks.finish(await env.query(checks.program.b)))
    finally:
        if checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure'] = str(checks.pipeline.failure)
        evidence.setdefault('arbitration',dict(blocked=checks.blocked_ticks,
            accepted=checks.accepted_ticks,overlap=checks.overlap_ticks,patches=checks.patch_offers))


async def run_burst(agent,profile,coverage,evidence):
    checks = BurstChecks(profile,coverage)
    try:
        async with experiment(agent,checks) as original:
            env = Program(agent,original.observation,original.anchor,checks.program.a)
            async with main_learning_evidence(env,evidence):
                await env.controls(ubtb=True)
                await env.feedback(await env.query(checks.program.loop),
                    Outcome(4,checks.program.loop,Kind.DIRECT,True,mispredict=True))
                env.anchor = await env.query(checks.program.a)
                await env.controls(ubtb=False)
                first = await prepare_sources(env)
                sources = (first,await env.query(checks.program.x),await env.query(checks.program.b))
                await env.controls(ubtb=True)
                await env.stream_feedbacks(sources)
                fresh = (await env.query(checks.program.b),await env.query(checks.program.x))
                evidence.update(checks.finish_many(fresh))
    finally:
        if checks.pipeline is not None and checks.pipeline.failure is not None:
            evidence['first_failure'] = str(checks.pipeline.failure)
        evidence.setdefault('arbitration',dict(blocked=checks.blocked_ticks,accepted=checks.accepted_ticks,
            overlap=checks.overlap_ticks,patches=checks.patch_offers))
