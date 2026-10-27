"""Learn both, selectively reward/penalize one, freshly consume every owner."""
from bpuverify.bpu.env.short_context_ownership import short_context_env
from bpuverify.bpu.model.short_context_ownership import OWNERS


async def _exercise_short_context(agent, program, coverage):
    async with short_context_env(agent,program,coverage) as env:
        checks = env.checks
        for branch in OWNERS:
            checks.phase = 'normal-learning-' + branch
            await env.learn_branch(branch)
        checks.mark('distinct-branch-ownership',states=checks.states())
        checks.mark('shared-short-history',paths=len(program.paths))
        selected = program.selected
        other = next(branch for branch in OWNERS if branch!=selected)
        await env.select(selected)
        await env.settle()
        retained = checks.states()[other]
        checks.phase = 'selective-upper-protection'
        start = len(checks.learning)
        for _ in range(4):  # Two-bit protection range, not an elapsed delay.
            view = await env.base(selected,taken=True)
            await view.set_main(early=False,target=False)
            await env.short_query(next(path for path in program.paths if path.branch==selected))
            updates = checks.learning[start:]
            changed = any(row['branch']==selected and row['kind']=='reward' and row['after']>row['before'] for row in updates)
            held = any(row['branch']==selected and row['kind']=='reward' and row['before']==row['after']==3 for row in updates)
            if changed and held:break
        checks.check(True,changed,'selected original genuinely gains protection before boundary holding')
        checks.check(True,held,'continued original correction holds protection at the upper bound')
        checks.mark('selective-protection-learning',events=len(updates))
        checks.mark('upper-protection-hold',protection=checks.states()[selected][1])
        checks.check(retained,checks.states()[other],'other branch is unchanged by selected rewards and base steering')
        checks.phase = 'short-penalty-separate-long-context'
        view = await env.select(selected)
        await view.set_main(early=True)
        before = len(checks.learning),len(checks.long_allocations)
        source = await view.visit(program.penalty(selected))
        await env.settle()
        penalties = [row for row in checks.learning[before[0]:] if row['branch']==selected and row['kind']=='penalty']
        allocations = checks.long_allocations[before[1]:]
        checks.check(1,len(penalties),'one owned short error changes only its original protection')
        checks.check((3,2),(penalties[0]['before'],penalties[0]['after']),'short error releases upper protection')
        checks.check(1,len(allocations),'the same short error permits one independently owned longer record')
        checks.check(program.penalty(selected).read_indices[1],allocations[0]['index'],
                     'longer allocation cannot mask either original short-consumer path')
        checks.mark('short-penalty-with-owned-long-allocation',source_tick=source.meta_tick,**allocations[0])
        checks.check(retained,checks.states()[other],'selected error and legal longer learning preserve the other branch')
        checks.mark('unrelated-branch-preserved',branch=other,state=retained)
        checks.phase = 'final-consumers'
        for branch in OWNERS:
            await env.base(branch,taken=False)
            for path in program.paths:
                if path.branch==branch:await env.short_query(path)
        checks.mark('fresh-both-history-consumers',consumers=4)
    return checks


async def check_short_context_ownership(agent, program, coverage):
    checks = await _exercise_short_context(agent,program,coverage)
    # Credit follows the complete passive scope, including PHR summary and
    # monitor teardown. An error during scope exit cannot leave checked bins.
    try:
        checks.finish_sharing()
    except BaseException as error:
        coverage.evidence = dict(checks.summary(),status='FAIL',
            first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:
        coverage.evidence = dict(checks.summary(),status='PASS')


async def _short_boundary(env,branch,*,taken):
    """A new correct opposition earns/holds confidence, not a timed wait."""
    c=env.checks
    path=next(item for item in env.program.paths if item.branch==branch)
    boundary=7 if taken else 0
    start=len(c.learning)
    for _ in range((7+1)+(3+1)):
        view=await env.base(branch,taken=not taken)
        await view.set_main(early=taken,target=False)
        source=await view.visit(path)
        await env.settle()
        c.direction_consumer(source,path,taken=taken)
        held=any(row['branch']==branch and row['kind']=='reward'
            and row['before']==row['after']==3 and row['counter_before']==row['counter_after']==boundary
            for row in c.learning[start:])
        if held:
            c.check((boundary,3),c.states()[branch],'declared direction and protection both hold at their boundary')
            return
    raise AssertionError('distinct correct original feedback did not establish direction/protection boundary')


async def _all_short_consumers(env,phase,*,selected_taken):
    c=env.checks
    c.phase=phase
    for branch in OWNERS:
        taken=selected_taken and branch==env.program.selected
        view=await env.base(branch,taken=not taken)
        await view.set_main(early=taken,target=False)
        for path in env.program.paths:
            if path.branch!=branch:continue
            source=await view.visit(path)
            c.direction_consumer(source,path,taken=taken)
            await env.settle()


async def _short_storage_boundary(env,phase):
    c=env.checks
    await env.active.visit(env.program.helper(env.active.program.branch))
    await env.settle()
    indices={identity.index for identity in c.identities.values()}
    def complete(checker):
        short=checker.model.sources.short
        pending=any(version.sequence in short.updates[0].dirty and version.index in indices
            for version in short.updates[0].outstanding)
        return short.offered is None and short.learning is None and c.pending_protection is None and not pending
    await env.observation.wait('short-direction-original-SRAM-service-complete',complete)
    c.check_storage(phase)


async def _reverse_short(env,*,taken):
    c,p=env.checks,env.program
    branch=p.selected
    view=await env.select(branch)
    counter,protection=c.states()[branch]
    plan=p.reversal(branch,counter=counter,protection=protection,taken=taken)
    # The original states determine the plan before Main is changed. Helper
    # steering has a different short identity and cannot teach this record.
    view=await env.base(branch,taken=not taken)
    await view.set_main(early=taken,target=False)
    for path,before,after in plan:
        start=len(c.learning)
        source=await view.visit(path)
        await env.settle()
        c.changed_by_original(source,path,before,after,start,taken=taken)


async def check_short_direction_lifetime(agent,program,coverage):
    from bpuverify.bpu.bundle.history_working_set import short_storage_binding
    from bpuverify.bpu.checker.short_context_ownership import ShortDirectionChecks
    async with short_context_env(agent,program,coverage,checks_factory=ShortDirectionChecks,
            binding_factory=lambda agent,**options:short_storage_binding(agent,program.storage_paths,**options)) as env:
        c=env.checks
        for branch in program.learning_order:
            c.phase='learn-and-stabilize-original-NT'
            await env.learn_branch(branch)
            await _short_boundary(env,branch,taken=False)
        c.mark('real-shared-short-owners',paths=len(program.paths))
        await _all_short_consumers(env,'initial-NT-consumers',selected_taken=False)
        c.mark('both-initial-NT-consumers',consumers=4)
        other=next(branch for branch in OWNERS if branch!=program.selected)
        retained=c.states()[other]
        c.phase='selected-NT-to-T'
        await _reverse_short(env,taken=True)
        c.mark('owned-opposite-guidance',originals=len(c.direction_changes))
        c.phase='selected-T-boundaries'
        await _short_boundary(env,program.selected,taken=True)
        c.mark('T-protection-and-direction-boundaries',state=c.states()[program.selected])
        c.check(retained,c.states()[other],'other branch remains unchanged during the selected direction reversal')
        await _short_storage_boundary(env,'selected-T-other-NT')
        c.mark('actual-SRAM-after-turnaround',records=2)
        await _all_short_consumers(env,'mixed-T-NT-consumers',selected_taken=True)
        c.mark('selected-real-T-consumers',consumers=2)
        c.mark('mixed-directions-preserved',consumers=4)
        c.phase='selected-T-to-NT'
        await _reverse_short(env,taken=False)
        c.phase='selected-restored-NT-boundaries'
        await _short_boundary(env,program.selected,taken=False)
        c.mark('NT-protection-and-direction-boundaries',state=c.states()[program.selected])
        c.check(retained,c.states()[other],'restoring the selected branch still preserves the independent branch')
        await _short_storage_boundary(env,'both-restored-NT')
        await _all_short_consumers(env,'final-direction-consumers',selected_taken=False)
        c.mark('selected-real-NT-restoration',consumers=2)
        c.mark('all-final-short-consumers',consumers=4)
        c.mark('longer-companions-do-not-mask-short',companions=len(c.long_allocations))
        c.mark('immutable-original-evidence',originals=len(c.originals))
    try:
        c.finish_direction()
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence=dict(c.summary(),status='PASS')


async def check_short_cross_branch_working_set(agent,program,coverage):
    from bpuverify.bpu.bundle.history_working_set import short_storage_binding
    from bpuverify.bpu.checker.short_context_ownership import ShortCrossBranchChecks
    from bpuverify.bpu.env.short_context_ownership import (
        working_set_direction_boundary,working_set_reverse,working_set_consumers)
    async with short_context_env(agent,program,coverage,checks_factory=ShortCrossBranchChecks,
            binding_factory=lambda agent,**options:short_storage_binding(agent,program.storage_paths,**options)) as env:
        c=env.checks
        for branch in program.learning_order:
            view=await env.select(branch)
            for path in program.paths:
                if path.branch!=branch:continue
                c.phase='normal-multi-path-admission'
                await view.short_guidance(taken=False)
                def ready(source):
                    value=view.snapshot_provider(source,2)
                    return value is not None and value[0]==0 and not value[2]
                await view.learn_until(path,ready,'normal learning establishes this original short NT experience')
                await working_set_direction_boundary(env,path,taken=False)
        c.mark('genuine-two-branch-paths',branches=2,identities=len(c.ledgers))
        c.mark('coexisting-short-experience',identities=len(c.ledgers))
        await working_set_consumers(env,'initial-working-set-consumers',set())
        c.phase='build-opposed-mixed-experience'
        for path in program.mixed:
            await working_set_reverse(env,path,taken=True)
            await working_set_direction_boundary(env,path,taken=True)
        mixed={path.ordinal for path in program.mixed}
        await _short_storage_boundary(env,'mixed')
        c.mark('real-storage-pressure',identities=len(c.ledgers))
        await working_set_consumers(env,'mixed-working-set-consumers',mixed)
        c.mark('mixed-branch-owned-directions',taken=len(mixed),not_taken=len(program.paths)-len(mixed))
        path=program.selected_path
        c.phase='selected-owner-NT-to-T'
        await working_set_reverse(env,path,taken=True)
        await working_set_direction_boundary(env,path,taken=True)
        await _short_storage_boundary(env,'turned')
        await working_set_consumers(env,'turned-working-set-consumers',mixed|{path.ordinal})
        c.mark('selected-reversal',path=path.ordinal)
        c.phase='selected-owner-T-to-NT'
        await working_set_reverse(env,path,taken=False)
        await working_set_direction_boundary(env,path,taken=False)
        await _short_storage_boundary(env,'final')
        await working_set_consumers(env,'final-working-set-consumers',mixed)
        for rule in ('selected-restoration','other-branch-preserved','other-paths-preserved',
                'original-feedback-once','no-longer-provider-substitution','SRAM-and-fresh-all-consumers','immutable-originals'):
            c.mark(rule,identities=len(program.paths))
    try:c.finish_working_set()
    except BaseException as error:
        coverage.evidence=dict(c.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence=dict(c.summary(),status='PASS')
