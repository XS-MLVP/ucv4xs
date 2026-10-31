"""Own actual sources, restore a call prefix, then return naturally to its caller."""
from copy import deepcopy

from suites.frontend.bpu.bpu.env.ras.retirement import BpuRetirement
from suites.frontend.bpu.bpu.env.ras.semantic import RasSemanticEnvironment
from suites.frontend.bpu.bpu.env.ras.program import learn_sites
from suites.frontend.bpu.runtime.wait import wait_condition
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.model.ras.nested_recursion import (
    OUTER, INNER, OUTER_RETURN, INNER_RETURN, PROFILES, expanded_returns, sites)


async def collect_recursive_calls(retirement, semantic, outer, boundary):
    """Associate the mixed-PC prefix, including its already collected outer call.

    The production uniform-PC collector deliberately checks ALL call actions
    against one PC. Reusing it here would incorrectly discard the outer call.
    """
    agent, wait = retirement.agent, semantic.wait
    collected = [await wait(agent.next_transaction(start_pc=INNER, after_tick=boundary),
                            'actual recursive-call source') for _ in range(10)]
    await wait(agent.set_ready(prediction=False, meta=True), 'hold younger recursive requests')
    await wait(retirement.coherent.drain(), 'associate all older mixed-PC calls')
    inner = sorted(list(collected) + [source for source in retirement.phr.association.completed
        if source.prediction_tick > boundary and source.meta.perf.start_pc == INNER],
        key=lambda source: source.meta_tick)
    ticks = [outer.meta_tick] + [source.meta_tick for source in inner]
    retirement.checker.check(len(ticks), len(set(ticks)), phase='unique mixed-PC call sources')
    actual = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
              and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 2]
    retirement.checker.check(ticks, actual, phase='every outer and recursive call has its exact source')
    return inner


async def check_with_agent(agent, calls, coverage, evidence):
    if calls not in PROFILES:
        raise ValueError('declared recursive lifetime required')
    originals = []
    async with RasSemanticEnvironment(agent, return_pc=INNER_RETURN) as semantic, BpuRetirement(
            agent, semantic=semantic.reference) as retirement:
        wait = semantic.wait
        sources = await learn_sites(retirement, semantic, OUTER, sites())
        boundary = await wait(agent.redirect(BpuRedirect(OUTER, sources[OUTER].meta.redirect)),
                              'start actual outer call before recursion')
        await wait(agent.set_ready(prediction=True, meta=True), 'accept outer and recursive calls')
        outer = await wait(agent.next_transaction(start_pc=OUTER, after_tick=boundary), 'actual outer-call source')
        inner = await collect_recursive_calls(retirement, semantic, outer, boundary)
        retirement.checker.check(True, len(inner) > calls, phase='real younger recursive suffix exists')
        semantic.reference.source_expected(outer)
        checkpoint = inner[calls]
        prefix = semantic.reference.owned_program(checkpoint)
        retirement.checker.check((calls + 1, calls + 2),
            (prefix.calls, len(prefix.frames)), phase='one outer plus exactly declared recursive frames')
        coverage.reached('distinct-outer-and-recursive-sources', outer_tick=outer.meta_tick,
                         recursive_ticks=[item.meta_tick for item in inner[:calls]])
        for source in (outer, *inner[:calls], checkpoint):
            originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
        await wait(retirement.retire_many([(outer, 2)] + [(source, 2) for source in inner[:calls]]),
                   'retire only genuinely surviving calls')
        coverage.reached('all-live-calls-retired', count=calls + 1)
        boundary = await wait(agent.redirect(BpuRedirect(INNER_RETURN, checkpoint.meta.redirect)),
                              'cancel younger recursive suffix using its real pre-call checkpoint')
        def restored():
            semantic.reference.raise_failure()
            model = semantic.reference.model
            return model.program == prefix and model.pending_recovery is None
        await wait(wait_condition(agent.dut.clock, sample=restored, satisfied=bool,
            name='ras.owned-nested-prefix-recovery-compared', timeout_cycles=128),
            'registered source prefix recovery compared against the complete actual state')
        coverage.reached('owned-prefix-restored', source_tick=checkpoint.meta_tick,
                         surviving_calls=prefix.calls)
        await wait(agent.set_ready(prediction=True, meta=True), 'consume complete genuine return chain')
        collected_returns, continuation = [], None
        for _ in range(calls + 2):  # Every live return plus its neutral continuation.
            source = await wait(agent.next_transaction(after_tick=boundary, limit=4 * (calls + 1)),
                                'next original return or outer continuation, without discarding another PC')
            if source.meta.perf.start_pc == OUTER_RETURN:
                continuation = source
                break
            retirement.checker.check(INNER_RETURN, source.meta.perf.start_pc,
                                     phase='natural recursive return instruction before the outer continuation')
            collected_returns.append(source)
        retirement.checker.check(True, continuation is not None, phase='all returns reach their outer continuation')
        await wait(agent.set_ready(prediction=False, meta=True), 'hold neutral continuation')
        await wait(retirement.coherent.drain(), 'observe all older actual return sources')
        semantic.reference.raise_failure()
        returns = sorted(collected_returns + [source for source in retirement.phr.association.completed
            if source.prediction_tick > boundary and source.meta.perf.start_pc == INNER_RETURN],
            key=lambda source: source.meta_tick)
        wanted = expanded_returns(calls)
        actual = tuple(source.prediction.target for source in returns)
        retirement.checker.check(len(wanted), len(returns), phase='one actual S3 source per live logical return')
        actual_spec = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
                       and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 1]
        retirement.checker.check([source.meta_tick for source in returns], actual_spec,
                                 phase='all actual speculative returns associated exactly once')
        # S1 can differ from the final return repair. Exact S3 source ticks,
        # never a nearby same-PC sample, identify each complete actual target.
        parents = {row['tick']: row['parent'] for row in retirement.phr.records}
        final_targets = tuple(parents[source.meta_tick]['s3_target'] for source in returns)
        retirement.checker.check(wanted, final_targets, phase='expanded logical return-address sequence at actual S3')
        retirement.checker.check([INNER_RETURN] * len(returns),
            [parents[source.meta_tick]['s3_pc'] for source in returns], phase='same genuine return instruction owns each target')
        semantic.reference.raise_failure()
        retirement.checker.check(calls + 1, semantic.reference.counts['return-consumers'],
                                 phase='every recursive and outer return had an owned final consumer')
        retirement.checker.check((1, 0), (len(semantic.reference.model.program.frames),
            semantic.reference.model.program.head.address), phase='all live semantic frames consumed without bottom return')
        retirement.checker.check(OUTER_RETURN, continuation.meta.perf.start_pc,
                                 phase='natural control flow reached the different outer caller')
        coverage.reached('every-inner-return-consumed', count=calls)
        coverage.reached('distinct-outer-return-consumed', target=OUTER_RETURN,
                         source_tick=returns[-1].meta_tick, continuation_tick=continuation.meta_tick)
        for source in returns:
            originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
        await wait(retirement.retire_many([(source, 1) for source in returns]),
                   'retire every genuine return once, in original order')
        coverage.reached('every-return-retired-once', count=len(returns))
        retirement.checker.check((0, 0, 0), tuple(retirement.checker.reference.projection()[key]
            for key in ('top', 'ssp', 'sctr')), phase='committed stack is the original reset sentinel')
        retirement.checker.check(2 * (calls + 1), len(retirement.checker.applied),
                                 phase='one committed update for every live call and return')
        semantic.reference.finish()
        coverage.reached('complete-committed-state-restored', applied=len(retirement.checker.applied))
        retirement.checker.check(True, all(source.meta.resolve == resolve and source.meta.redirect == redirect
            for source, resolve, redirect in originals), phase='all exact original metadata remains immutable')
        coverage.reached('immutable-originals', count=len(originals))
        evidence.update(status='PASS', calls=calls, outer_pc=OUTER, inner_pc=INNER,
            outer_return=OUTER_RETURN, inner_return=INNER_RETURN,
            expected_return_targets=wanted, actual_s3_return_targets=final_targets, initial_prediction_targets=actual,
            exact_return_sources=[source.meta_tick for source in returns],
            real_checkpoint_tick=checkpoint.meta_tick,
            applied=len(retirement.checker.applied), reference=dict(calls=semantic.reference.model.program.calls,
                live_frames=len(semantic.reference.model.program.frames),
                final_group=semantic.reference.model.program.head.group,
                final_repeat=semantic.reference.model.program.head.repeat,
                retirements=semantic.reference.model.retirements),
            committed=retirement.checker.reference.native(), immutable_originals=True)
    coverage.finish()  # Both passive scopes and final PHR/retirement checks exited.
