"""Real source collection, capacity-safe retirement and natural return flow."""
from copy import deepcopy

from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.env.ras.semantic import RasSemanticEnvironment
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining
from bpuverify.common.env.wait import wait_condition
from bpuverify.bpu.model.ras.wrapped_recursion import (
    PREFIX, INNER, INNER_RETURN, PARENT_RETURN, SURVIVING_TOP,
    PROFILES, return_targets, sites, committed, validate)


async def learn_quiet_sites(retirement, semantic):
    """Learn only after cold-source work drains, avoiding a known gate defect.

    Disabled hot calls are already a retained strict-XFAIL contract. They are
    not needed to establish this committed-wrap lifetime. No oracle or DUT
    state is reset/seeded to conceal their effect; prevent that setup stimulus.
    """
    agent, wait = retirement.agent, semantic.wait
    await wait(agent.reset(PREFIX[0]), 'reset for independent deep-call program')
    cold = await wait(agent.next_transaction(start_pc=PREFIX[0]), 'initial genuine cold checkpoint')
    await wait(agent.set_ready(prediction=False, meta=True), 'hold initial cold preparation')
    await wait(retirement.coherent.drain(), 'drain initial cold work')
    await wait(agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
        ittage=False, ras=False, mbtb=True, settle=True), 'isolate Main before instruction learning')
    sources = {}
    for pc, target, kind, action in sites():
        boundary = await wait(agent.redirect(BpuRedirect(pc, cold.meta.redirect)),
                              'recover to the next unlearned instruction while held')
        await wait(agent.set_ready(prediction=True, meta=True), 'accept a real cold instruction source')
        cold = await wait(agent.next_transaction(start_pc=pc, after_tick=boundary),
                          'next exact cold program source')
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger work before learning a hot call')
        await wait(retirement.coherent.drain(), 'all old cold work observed before instruction changes')
        sources[pc] = cold
        await wait(agent.train(BpuTraining(pc, 15, target, cold.meta.resolve,
            branch_type=kind, ras_action=action)), 'learn actual instruction with no active cold request')
    await wait(agent.configure_predictors(ras=True, settle=True), 'enable the actual return-stack program')
    return sources


async def check_with_agent(agent, calls, coverage, evidence):
    validate(calls)
    originals = []
    async with RasSemanticEnvironment(agent, return_pc=INNER_RETURN) as semantic, BpuRetirement(
            agent, semantic=semantic.reference) as retirement:
        wait, check = semantic.wait, retirement.checker.check
        sources = await learn_quiet_sites(retirement, semantic)
        boundary = await wait(agent.redirect(BpuRedirect(PREFIX[0], sources[PREFIX[0]].meta.redirect)),
                              'start genuine deep call chain')
        await wait(agent.set_ready(prediction=True, meta=True), 'accept deep call prefix')
        prefix = [await wait(agent.next_transaction(start_pc=pc, after_tick=boundary),
                             'next actual caller in declared deep program') for pc in PREFIX]
        await wait(agent.set_ready(prediction=False, meta=True), 'hold younger recursive growth')
        await wait(retirement.coherent.drain(), 'associate every older deep/recursive call')
        initial_inner = []
        # Consume each already associated source through the public accessor;
        # do not mutate, replace or clear the association queue.
        for _ in range(len(retirement.phr.association.completed)):
            source = await wait(agent.next_transaction(after_tick=boundary), 'already accepted recursive source')
            check(INNER, source.meta.perf.start_pc, phase='only recursion follows the deep prefix')
            initial_inner.append(source)
        coverage.reached('actual-deep-call-sources', count=len(prefix))
        await wait(retirement.retire_many([(source, 2) for source in prefix]),
                   'retire genuine outer calls before accepting more recursive versions')
        check(len(PREFIX), len(retirement.checker.applied), phase='outer prefix retired exactly once')
        coverage.reached('older-prefix-retired-before-growth', count=len(prefix))
        await wait(agent.set_ready(prediction=True, meta=True), 'resume the existing recursive stream')
        inner = list(initial_inner)
        for _ in range(max(PROFILES) + 1 - len(inner)):
            inner.append(await wait(agent.next_transaction(start_pc=INNER, after_tick=boundary),
                                    'actual recursive source for a bounded checkpoint'))
        await wait(agent.set_ready(prediction=False, meta=True), 'stop younger recursive admission')
        await wait(retirement.coherent.drain(), 'associate every remaining recursive source')
        inner.extend(source for source in retirement.phr.association.completed
                     if source.prediction_tick > boundary and source.meta.perf.start_pc == INNER)
        inner.sort(key=lambda source: source.meta_tick)
        ticks = [source.meta_tick for source in (*prefix, *inner)]
        actual_calls = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
                        and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 2]
        check((len(ticks), ticks), (len(set(ticks)), actual_calls), phase='every deep and recursive call owns its exact S3 source')
        check(True, len(inner) > calls, phase='genuine unused checkpoint after the surviving recursive prefix')
        checkpoint = inner[calls]
        program = semantic.reference.owned_program(checkpoint)
        check(len(PREFIX) + calls, program.calls, phase='declared actual pre-call source owns the exact recursive prefix')
        for source in (*prefix, *inner[:calls], checkpoint):
            originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
        await wait(retirement.retire_many([(source, 2) for source in inner[:calls]]),
                   'retire only the surviving recursive prefix')
        before_returns = committed(calls)
        check(before_returns.native(), retirement.checker.reference.native(), phase='complete committed wrap and recursive boundary')
        check((0, 7) if calls == 8 else (1, 0),
            (before_returns.head, before_returns.projection()['sctr']), phase='full repeated group or its next group')
        coverage.reached('committed-storage-really-wrapped', evicted=len(before_returns.evicted))
        coverage.reached('declared-repeat-boundary', calls=calls)
        boundary = await wait(agent.redirect(BpuRedirect(INNER_RETURN, checkpoint.meta.redirect)),
                              'cancel younger recursion using an actual owned checkpoint')
        def restored():
            semantic.reference.raise_failure()
            model = semantic.reference.model
            return model.program == program and model.pending_recovery is None
        await wait(wait_condition(agent.dut.clock, sample=restored, satisfied=bool,
            name='ras.wrapped-recursive-prefix-compared', timeout_cycles=128),
            'actual restored prefix compared with the independent source program')
        coverage.reached('owned-recursive-prefix-restored', source_tick=checkpoint.meta_tick)
        await wait(agent.set_ready(prediction=True, meta=True), 'consume all recursive returns and one parent return')
        returns, continuation = [], None
        for _ in range(len(return_targets(calls)) + 1):
            source = await wait(agent.next_transaction(after_tick=boundary, limit=4 * (calls + 1)),
                                'next original return or different-address parent continuation')
            if source.meta.perf.start_pc == PARENT_RETURN:
                continuation = source
                break
            check(INNER_RETURN, source.meta.perf.start_pc, phase='return instruction owns the complete unwind')
            returns.append(source)
        check(True, continuation is not None, phase='natural return reaches its different-address parent')
        await wait(agent.set_ready(prediction=False, meta=True), 'hold neutral parent continuation')
        await wait(retirement.coherent.drain(), 'all older return operations associated')
        returns.extend(source for source in retirement.phr.association.completed
                       if source.prediction_tick > boundary and source.meta.perf.start_pc == INNER_RETURN)
        returns.sort(key=lambda source: source.meta_tick)
        actual_return_ticks = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
            and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 1]
        check([source.meta_tick for source in returns], actual_return_ticks, phase='every return has a unique original S3 source')
        parents = {row['tick']: row['parent'] for row in retirement.phr.records}
        targets = tuple(parents[source.meta_tick]['s3_target'] for source in returns)
        check(return_targets(calls), targets, phase='all recursive targets followed by the distinct parent return target')
        check(len(targets), semantic.reference.counts['return-consumers'], phase='all final return consumers independently checked')
        coverage.reached('all-recursive-returns-consumed', count=calls)
        coverage.reached('distinct-parent-return-consumed', target=PARENT_RETURN)
        for source in returns:
            originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
        await wait(retirement.retire_many([(source, 1) for source in returns]),
                   'retire all actual recursive and parent returns in order')
        expected = committed(calls, returned=True)
        check(expected.native(), retirement.checker.reference.native(), phase='every committed cell and retained older caller')
        check(SURVIVING_TOP, retirement.checker.reference.projection()['top'], phase='different older caller remains at the top')
        check(SURVIVING_TOP, semantic.reference.model.projection['top'], phase='actual semantic top agrees after bounded unwind')
        coverage.reached('retained-older-callers-preserved', count=len(expected.groups))
        applied = len(PREFIX) + calls + len(targets)
        check(applied, len(retirement.checker.applied), phase='all and only live calls and returns retired once')
        coverage.reached('every-live-operation-retired-once', count=applied)
        check(True, all(source.meta.resolve == resolve and source.meta.redirect == redirect
            for source, resolve, redirect in originals), phase='original metadata immutable across capacity wrap')
        coverage.reached('immutable-originals', count=len(originals))
        semantic.reference.finish()
        evidence.update(status='PASS', calls=calls, prefix_call_count=len(prefix),
            actual_return_targets=targets, expected_return_targets=return_targets(calls),
            exact_return_sources=[source.meta_tick for source in returns], checkpoint_tick=checkpoint.meta_tick,
            committed_before_returns=before_returns.native(), committed_after_returns=expected.native(),
            actual_applied=applied, retained_older_callers=len(expected.groups),
            surviving_top=SURVIVING_TOP, original_sources=len(originals), immutable_originals=True,
            excludes_evicted_oldest_return=True)
    coverage.finish()
