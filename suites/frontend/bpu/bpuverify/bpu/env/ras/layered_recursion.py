"""Public transaction driving with existing passive RAS/PHR/commit checkers."""
from copy import deepcopy

from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.env.ras.semantic import RasSemanticEnvironment
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining
from bpuverify.common.env.wait import wait_condition
from bpuverify.bpu.model.ras.layered_recursion import ROOT, LAYERS, ROOT_RETURN, POSITION
from bpuverify.bpu.checker.ras.layered_recursion import compare_returns


async def learn_sites(retirement, semantic, program, *, root_pc=ROOT, position=POSITION):
    """Hold/drain real cold work before learning, avoiding disabled hot calls."""
    agent, wait = retirement.agent, semantic.wait
    await wait(agent.reset(root_pc), 'reset layered recursive program')
    cold = await wait(agent.next_transaction(start_pc=root_pc), 'initial real cold checkpoint')
    await wait(agent.set_ready(prediction=False, meta=True), 'hold cold preparation')
    await wait(retirement.coherent.drain(), 'drain initial cold sources')
    await wait(agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
        ittage=False, ras=False, mbtb=True, settle=True), 'learn instructions with RAS disabled')
    sources = {}
    for pc, target, kind, action in program.sites():
        boundary = await wait(agent.redirect(BpuRedirect(pc, cold.meta.redirect)), 'recover to unlearned instruction')
        await wait(agent.set_ready(prediction=True, meta=True), 'accept exact cold source')
        cold = await wait(agent.next_transaction(start_pc=pc, after_tick=boundary), 'real cold instruction metadata')
        await wait(agent.set_ready(prediction=False, meta=True), 'hold younger cold requests')
        await wait(retirement.coherent.drain(), 'drain cold work before learning a hot call')
        sources[pc] = cold
        await wait(agent.train(BpuTraining(pc, position, target, cold.meta.resolve,
            branch_type=kind, ras_action=action)), 'learn actual indirect call or return instruction')
    await wait(agent.configure_predictors(ras=True, settle=True), 'enable unchanged full recursive lifetime')
    return sources


async def collect_layer(retirement, semantic, pc, count, boundary, root_source=None):
    agent, wait, check = retirement.agent, semantic.wait, retirement.checker.check
    selected = [await wait(agent.next_transaction(start_pc=pc, after_tick=boundary),
                           'real recursive source and younger cancellable suffix') for _ in range(count + 1)]
    await wait(agent.set_ready(prediction=False, meta=True), 'hold younger recursive growth')
    await wait(retirement.coherent.drain(), 'associate all actual recursive sources')
    selected.extend(source for source in retirement.phr.association.completed
                    if source.prediction_tick > boundary and source.meta.perf.start_pc == pc)
    selected.sort(key=lambda source: source.meta_tick)
    ticks = ([root_source.meta_tick] if root_source is not None else []) + [source.meta_tick for source in selected]
    actual = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
        and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 2]
    check((len(ticks), ticks), (len(set(ticks)), actual), phase='every-root-and-recursive-call-has-one-owned-S3-source')
    check(True, len(selected) > count, phase='actual-younger-calls-exist-to-cancel')
    return selected


async def check_with_agent(agent, program, coverage, evidence, *, root_pc=ROOT, layer_pcs=LAYERS,
                           root_return=ROOT_RETURN, position=POSITION):
    originals, corrections, call_ticks, boundaries = [], [], [], []
    async with RasSemanticEnvironment(agent) as semantic, BpuRetirement(
            agent, semantic=semantic.reference) as retirement:
        wait, check = semantic.wait, retirement.checker.check
        sources = await learn_sites(retirement, semantic, program,root_pc=root_pc,position=position)
        boundary = await wait(agent.redirect(BpuRedirect(root_pc, sources[root_pc].meta.redirect)), 'start root caller')
        await wait(agent.set_ready(prediction=True, meta=True), 'accept genuine root and recursive calls')
        root = await wait(agent.next_transaction(start_pc=root_pc, after_tick=boundary), 'actual root-call source')
        originals.append((root, deepcopy(root.meta.resolve), deepcopy(root.meta.redirect)))
        call_ticks.append(root.meta_tick)
        for layer, (pc, count) in enumerate(zip(layer_pcs, program.counts,strict=True)):
            calls = await collect_layer(retirement, semantic, pc, count, boundary, root if layer == 0 else None)
            for source in calls[:count]:
                originals.append((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)))
                call_ticks.append(source.meta_tick)
            chosen = calls[count - 1]
            prefix = semantic.reference.owned_program(chosen)
            addresses = program.call_addresses(layer + 1)
            check(tuple([0] + [2 * value for value in addresses[:-1]]),
                tuple(frame.address for frame in prefix.frames), phase='original-final-call-owns-exact-older-logical-prefix')
            older = ([(root, 2)] if layer == 0 else []) + [(source, 2) for source in calls[:count - 1]]
            if older:
                await wait(retirement.retire_many(older), 'retire all older calls before correcting final indirect target')
            target = layer_pcs[layer + 1] if layer + 1 < len(layer_pcs) else pc + 16
            previous_calls = semantic.reference.model.program.calls
            boundary = await wait(agent.redirect(BpuRedirect(target, chosen.meta.redirect,
                cfi_pc=(pc // 8) * 8 + position, branch_type=3, ras_action=2)),
                'correct actual final indirect call target and redo its call exactly once')
            expected_addresses = tuple([0] + [2 * value for value in addresses])
            def restored():
                semantic.reference.raise_failure()
                model = semantic.reference.model
                return model.pending_recovery is None and model.program.calls == len(addresses) and (
                    tuple(frame.address for frame in model.program.frames) == expected_addresses)
            await wait(wait_condition(agent.dut.clock, sample=restored, satisfied=bool,
                name='ras.layered-owned-call-correction-compared', timeout_cycles=128),
                'independently compared corrected logical call prefix')
            check(True, previous_calls > len(addresses), phase='correction-cancelled-real-younger-tail')
            await wait(retirement.retire_many([(chosen, 2)]), 'retire corrected original indirect call once')
            expected = program.committed(layers=layer + 1)
            check(expected.native(), retirement.checker.reference.native(), phase='complete-committed-state-after-each-recursive-layer')
            corrections.append(dict(pc=pc, target=target, original_tick=chosen.meta_tick,
                original_calls=prefix.calls, surviving_calls=len(addresses), cancelled_calls=previous_calls-len(addresses),
                committed=expected.native()))
            boundaries.append(boundary)
            evidence.update(corrections=deepcopy(corrections), live_call_sources=list(call_ticks))
            if layer + 1 < len(layer_pcs):
                await wait(agent.set_ready(prediction=True, meta=True), 'accept next distinct recursive layer')
        coverage.reached('distinct-recursive-layer-sources', source_ticks=call_ticks)
        coverage.reached('older-calls-retired-before-growth', live_calls=len(call_ticks))
        coverage.reached('owned-target-corrections', original_ticks=[row['original_tick'] for row in corrections])
        coverage.reached('no-duplicate-redone-call', surviving_calls=semantic.reference.model.program.calls)
        check(len(program.call_addresses()), len(retirement.checker.applied), phase='all-live-calls-and-only-live-calls-retired')
        coverage.reached('all-logical-calls-retained', count=len(call_ticks))
        state = program.committed()
        check((program.inner_calls-1)%8, state.projection()['sctr'], phase='full-or-nonzero-split-recursive-group')
        coverage.reached('innermost-repeat-boundary', repeat=state.projection()['sctr'])
        await wait(agent.set_ready(prediction=True, meta=True), 'consume complete natural mixed-PC return chain')
        returns, continuation = [], None
        for _ in range(len(program.return_targets) + 1):
            source = await wait(agent.next_transaction(after_tick=boundary, limit=4 * len(program.return_targets)),
                                'next original return without filtering another recursive PC')
            if source.meta.perf.start_pc == root_return:
                continuation = source
                break
            check(True, source.meta.perf.start_pc in tuple(pc + 16 for pc in layer_pcs),
                  phase='return-belongs-to-one-declared-recursive-body')
            returns.append(source)
        check(True, continuation is not None, phase='complete-return-chain-reaches-root-caller')
        await wait(agent.set_ready(prediction=False, meta=True), 'hold neutral root continuation')
        await wait(retirement.coherent.drain(), 'associate every older return source')
        returns.extend(source for source in retirement.phr.association.completed if source.prediction_tick > boundary
                       and source.meta.perf.start_pc in tuple(pc + 16 for pc in layer_pcs))
        returns.sort(key=lambda source: source.meta_tick)
        actual_ticks = [row['tick'] for row in retirement.checker.records if row['tick'] > boundary
            and row['spec']['valid'] and row['spec']['enable'] and row['spec']['action'] == 1]
        check([source.meta_tick for source in returns], actual_ticks, phase='every-return-has-a-unique-actual-S3-source')
        parents = {row['tick']: row['parent'] for row in retirement.phr.records}
        pcs = tuple(parents[source.meta_tick]['s3_pc'] for source in returns)
        targets = tuple(parents[source.meta_tick]['s3_target'] for source in returns)
        evidence.update(actual_return_pcs=pcs, actual_return_targets=targets,
                        exact_return_sources=[source.meta_tick for source in returns])
        compare_returns(check, program, pcs, targets)
        check(len(returns), semantic.reference.counts['return-consumers'], phase='every-final-return-consumer-checked')
        coverage.reached('complete-mixed-pc-return-chain', count=len(returns))
        coverage.reached('outer-return-identities-restored', targets=targets)
        originals.extend((source, deepcopy(source.meta.resolve), deepcopy(source.meta.redirect)) for source in returns)
        cursor, surviving_states = 0, []
        for count in (*program.counts[::-1], 1):
            chunk = returns[cursor:cursor + count]
            await wait(retirement.retire_many([(source, 1) for source in chunk]), 'retire next logical recursive layer only')
            cursor += count
            expected = program.committed(returned=cursor)
            check(expected.native(), retirement.checker.reference.native(), phase='inner-retirement-preserves-all-outer-repeat-counts')
            surviving_states.append(dict(returned=cursor, logical_survivors=len(program.call_addresses())-cursor,
                                         committed=expected.native()))
        coverage.reached('outer-repeat-counts-preserved', boundaries=[row['returned'] for row in surviving_states])
        check(2 * len(program.call_addresses()), len(retirement.checker.applied), phase='every-call-and-return-retired-once')
        coverage.reached('every-live-operation-retired-once', applied=len(retirement.checker.applied))
        check((0, 0, 0), tuple(retirement.checker.reference.projection()[key] for key in ('top', 'ssp', 'sctr')),
              phase='complete-logical-unwind-restores-reset-sentinel')
        check((1, 0), (len(semantic.reference.model.program.frames), semantic.reference.model.program.head.address),
              phase='no-extra-return-of-empty-semantic-stack')
        coverage.reached('complete-sentinel-state-restored')
        check(True, all(source.meta.resolve == resolve and source.meta.redirect == redirect
                        for source, resolve, redirect in originals), phase='all-original-metadata-remains-immutable')
        coverage.reached('immutable-originals', count=len(originals))
        semantic.reference.finish()
        evidence.update(status='PASS', program=program.state(), corrections=corrections,
            live_call_sources=call_ticks, exact_return_sources=[source.meta_tick for source in returns],
            actual_return_pcs=pcs, actual_return_targets=targets, surviving_states=surviving_states,
            applied=len(retirement.checker.applied), immutable_originals=True,
            semantic_retirements=semantic.reference.model.retirements, return_consumers=semantic.reference.counts['return-consumers'])
    coverage.finish()
