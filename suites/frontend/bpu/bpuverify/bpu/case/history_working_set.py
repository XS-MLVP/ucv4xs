"""History lifetime intent; execution and observation stay in env/checker."""
from bpuverify.bpu.env.history_working_set import history_working_set_env
from bpuverify.bpu.model.history_working_set import SHORT_POSITION


async def check_short_path_retention(agent,program,coverage):
    from bpuverify.bpu.bundle.history_working_set import short_path_retention_binding
    from bpuverify.bpu.checker.history_working_set import ShortPathRetentionChecks
    async with history_working_set_env(agent,program,coverage,checks_factory=ShortPathRetentionChecks,
            binding_factory=lambda agent,**options:short_path_retention_binding(agent,program,**options)) as env:
        c=env.checks
        await env.bootstrap()

        async def positive_base():
            await env.set_main(early=True)
            await env.learn_until(program.helper,lambda source:env.ahead_counter(source,SHORT_POSITION)==3,
                'a different short identity establishes the genuinely opposed early base')
            await env.set_main(early=False,target=False)

        def short_ready(source):
            value=env.snapshot_provider(source,SHORT_POSITION)
            early=c.pipeline.source_token(source).early.branch
            return value is not None and value[0]==0 and not value[2] and early.taken and early.position==12

        async def storage_boundary(phase):
            # A real helper traversal supplies ordinary service opportunities.
            # Completion follows independently pending learning, never waiting
            # for sampled SRAM to happen to equal the desired answer.
            await env.visit(program.helper)
            await env.pause()
            indices={identity.index for identity in c.short_identities.values()}
            def complete(checker):
                short=checker.model.sources.short
                pending=any(version.sequence in short.updates[0].dirty and version.index in indices
                    for version in short.updates[0].outstanding)
                return short.offered is None and short.learning is None and c.short_pending is None and not pending
            await env.observation.wait('short_original_learning_and_services_complete',complete)
            c.check_storage(phase)

        c.phase='admit-short-incoming-experience'
        for path in program.positives:
            await positive_base()
            source=await env.learn_until(path,short_ready,'a real early consumer uses its learned short NT record')
            c.short_consumer(source,path)
        c.mark('real-read-and-match-ancestors',paths=len(program.positives))
        c.mark('all-short-identities-learned',identities=len(c.short_ledgers))
        c.mark('short-not-long-consumers',consumers=len(c.short_consumers))
        selected=program.selected[0]
        other={key:value for key,value in c.short_states().items() if key!=selected.ordinal}
        start=len(c.short_learning)
        c.phase='selected-protection-and-direction-boundaries'
        for _ in range(4):  # Four protection levels, not an elapsed-cycle wait.
            await positive_base()
            source=await env.learn_until(selected,short_ready,'selected real short experience remains consumable')
            c.short_consumer(source,selected)
            events=[row for row in c.short_learning[start:] if row['path']==selected.ordinal]
            gain=any(row['kind']=='reward' and row['after']>row['before'] for row in events)
            hold=any(row['kind']=='reward' and row['before']==row['after']==3
                and row['counter_before']==row['counter_after']==0 for row in events)
            if gain and hold:break
        c.check(True,gain,'selected path genuinely gains protection')
        c.check(True,hold,'selected lower direction and upper protection both hold without wrapping')
        c.mark('selected-gains-protection',path=selected.ordinal)
        c.mark('selected-direction-and-protection-boundaries',path=selected.ordinal)
        c.check(other,{key:value for key,value in c.short_states().items() if key!=selected.ordinal},
            'rewarding one incoming path does not relearn its neighbors')
        c.mark('other-paths-preserved',identities=len(other))
        await storage_boundary('before-final-consumers')
        c.mark('native-SRAM-and-retention',identities=len(program.positives))
        c.phase='final-short-consumers'
        for path in program.positives:
            source=await env.visit(path)
            c.short_consumer(source,path)
        c.mark('fresh-all-path-consumers',consumers=len(program.positives))
        await storage_boundary('after-final-consumers')
        c.mark('immutable-original-sources',originals=len(c.originals))
    # PHR summary and passive-scope cleanup are also part of success. They
    # must finish before any checked bin is granted to the whole lifetime.
    try:
        c.finish()
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:
        coverage.evidence=dict(c.summary(),status='PASS')


async def _mixed_boundary(env,path,*,taken):
    """Stabilize direction; agreement may legitimately hold protection below 3."""
    c=env.checks
    start=len(c.short_learning)
    # The caller already installed the real outcome and opposed base. Fast
    # feedback also teaches that shared base; later agreement is neutral for
    # protection, while direction continues to learn. Re-steering the helper
    # here would add unrelated learning, not prove this lifetime any better.
    for _ in range(7+1):
        source=await env.visit(path)
        await env.short_settle()
        state=c.short_states()[path.ordinal]
        if state[0]==(7 if taken else 0):
            c.short_consumer(source,path,taken=taken)
            return
    c.check(True,False,dict(event='normal feedback reaches the declared direction boundary',
        path=path.ordinal,taken=taken,learning=c.short_learning[start:]))


async def _mixed_reverse(env,path,*,taken):
    c=env.checks
    await env.short_settle()
    before=c.short_states()
    counter,protection=before[path.ordinal]
    plan=env.program.reversal(path,counter=counter,protection=protection,taken=taken)
    c.declare_result(path,taken)
    await env.short_guidance(taken=taken)
    for original,old,new in plan:
        start=len(c.short_learning)
        source=await env.visit(original)
        await env.short_settle()
        c.changed_by_original(source,original,old,new,start)
    c.check({key:value for key,value in before.items() if key!=path.ordinal},
        {key:value for key,value in c.short_states().items() if key!=path.ordinal},
        'reversing one incoming experience preserves every other learned direction and protection')


async def _mixed_consumers(env,phase,positive):
    c=env.checks
    c.phase=phase
    # Group by actual outcome to avoid steering the helper for every read.
    # Both groups remain real fresh path traversals, not cached predictions.
    for taken in (False,True):
        paths=tuple(path for path in env.program.learning_order if (path.ordinal in positive)==taken)
        if not paths:continue
        await env.short_guidance(taken=taken)
        for path in paths:
            source=await env.visit(path)
            c.short_consumer(source,path,taken=taken)
            await env.short_settle()


async def check_short_mixed_lifetime(agent,program,coverage):
    from bpuverify.bpu.bundle.history_working_set import short_path_retention_binding
    from bpuverify.bpu.checker.history_working_set import ShortMixedPathChecks
    async with history_working_set_env(agent,program,coverage,checks_factory=ShortMixedPathChecks,
            binding_factory=lambda agent,**options:short_path_retention_binding(agent,program,**options)) as env:
        c=env.checks
        await env.bootstrap()
        c.phase='normal-independent-NT-learning'
        for path in program.learning_order:
            await env.short_guidance(taken=False)
            def ready(source):
                value=env.snapshot_provider(source,SHORT_POSITION)
                return value is not None and value[0]==0 and not value[2]
            await env.learn_until(path,ready,'normal learning creates a real short NT consumer')
            await _mixed_boundary(env,path,taken=False)
        c.mark('real-path-owners',identities=len(c.short_ledgers))
        await _mixed_consumers(env,'initial-short-consumers',set())
        c.mark('all-initial-NT-consumers',consumers=len(program.positives))
        c.phase='establish-mixed-experience'
        for path in program.mixed:
            await _mixed_reverse(env,path,taken=True)
            await _mixed_boundary(env,path,taken=True)
        mixed={path.ordinal for path in program.mixed}
        await env.short_storage_boundary('mixed')
        c.mark('mixed-SRAM-after-turnover',identities=len(program.positives))
        await _mixed_consumers(env,'mixed-short-consumers',mixed)
        c.mark('persistent-mixed-directions',taken=len(mixed),not_taken=len(program.positives)-len(mixed))
        selected=program.selected[0]
        c.phase='selected-NT-to-T'
        await _mixed_reverse(env,selected,taken=True)
        await _mixed_boundary(env,selected,taken=True)
        await env.short_storage_boundary('turned')
        await _mixed_consumers(env,'turned-short-consumers',mixed|{selected.ordinal})
        c.mark('selected-NT-to-T',path=selected.ordinal)
        c.phase='selected-T-to-NT'
        await _mixed_reverse(env,selected,taken=False)
        await _mixed_boundary(env,selected,taken=False)
        await env.short_storage_boundary('restored')
        c.mark('restored-SRAM-after-turnover',identities=len(program.positives))
        await _mixed_consumers(env,'final-short-consumers',mixed)
        c.mark('selected-T-to-NT',path=selected.ordinal)
        c.mark('unrelated-experience-preserved',identities=len(program.positives)-1)
        c.mark('original-learning-once',originals=len(c.direction_changes))
        c.mark('no-longer-substitution',provider=0)
        c.mark('fresh-all-final-consumers',consumers=len(program.positives))
        c.mark('immutable-originals',originals=len(c.originals))
    try:c.finish()
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence=dict(c.summary(),status='PASS')


async def check_history_working_set(agent, program, coverage):
    async with history_working_set_env(agent,program,coverage) as env:
        await env.bootstrap()
        await env.seed_short()
        for path in program.positives:
            await env.positive(path)
            env.checks.admitted.add(path.ordinal)
            if path == program.selected[0]:
                # Qualify distinguishable public behavior before growing the
                # workset. Lifetime credit still requires the complete run.
                await env.reverse(path)
                await env.restore(path)
        env.checks.reached_phase('long-history-admissions',identities=len(env.checks.admitted))
        env.checks.reached_phase('correct-opposition-reward',events=env.checks.ledger.transitions['reward'])
        for path in program.revisit:
            await env.positive(path)
        env.checks.reached_phase('upper-protection-hold',identities=len(program.positives))
        env.checks.reached_phase('retained-after-shadow-turnover',identities=len(program.positives))
        if program.profile == 'capacity-reverse':
            for helper in program.helpers:
                source = await env.negative_base(helper,require_provider=True)
                env.checks.direction(source,helper,taken=False,phase='maintenance-seed')
        for path in program.selected:
            await env.reverse(path)
            await env.observe_maintenance()
        env.checks.reached_phase('selective-penalty',identities=len(env.checks.penalized))
        env.checks.reached_phase('selected-direction-reversal',identities=len(env.checks.reversed_consumers))
        for path in program.revisit:
            await env.read_direction(path,taken=path not in program.selected,phase='mixed')
            env.checks.revisited.add(path.ordinal)
        env.checks.reached_phase('mixed-history-directions',consumers=len(env.checks.mixed_consumers),
                                 not_taken=len(program.selected),taken=len(program.positives)-len(program.selected))
        env.checks.reached_phase('untouched-identities-preserved',identities=len(program.positives)-len(program.selected))
        for path in program.selected:
            await env.restore(path)
            await env.observe_maintenance()
        env.checks.reached_phase('selective-recovery',identities=len(env.checks.recovered))
        env.checks.reached_phase('selected-direction-restoration',identities=len(env.checks.recovered))
        await env.set_main(early=False,target=True)
        env.checks.phase = 'late-all-positive-consumers'
        for path in program.revisit:
            source = await env.visit(path)
            env.checks.direction(source,path,taken=True,phase='restored')
        for path in program.short_consumers:
            source = await env.visit(path)
            value = env.checks.provider(source,path,SHORT_POSITION)
            env.checks.check((0,False),(value[0],value[2]),'late shared short prerequisite retains its own other position')
        for helper in program.helpers:await env.negative_base(helper,require_provider=True)
        env.checks.reached_phase('genuine-predecessor-paths',histories=len(env.checks.path_visits))
        env.checks.reached_phase('distinct-original-history-owners',sources=len(env.checks.visit_owners))
        env.checks.reached_phase('late-all-history-consumers',identities=len(env.checks.revisited))
        env.checks.finish()
