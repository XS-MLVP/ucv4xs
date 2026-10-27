"""High-index useful updates through real integrated program/feedback ancestry."""

from bpuverify.common.coverage.exports import write_functional_coverage
from collections import Counter
from dataclasses import asdict
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.case.bypass.public_readback import conditional_source_ways, public_readback_pair, training_tag_fold_pair
from bpuverify.bpu.checker.bypass.aging_scope import NonzeroChecks
from bpuverify.bpu.env.bypass.aging_scope import NonzeroObservation
from bpuverify.bpu.env.bypass.sparse import SparseProgramEnvironment
from bpuverify.bpu.coverage.bypass.high_index import collect_updates
from bpuverify.bpu.model.bypass.high_index import HIGH_INDEX_ROLES, base_alias, program
from bpuverify.bpu.model.bypass.model import payload
from bpuverify.bpu.model.bypass.sparse import qualifies_return_request
from bpuverify.bpu.model.abtb.alias import physical_index


HIGH_INDEX_CONTRACTS = ('independent-index-tag-ancestors', 'genuine-lower-provider-metadata',
    'high-row-allocation', 'high-row-increase', 'high-row-decrease', 'high-row-agreement-hold',
    'same-base-distinct-MicroTAGE-alias', 'original-provider-preserved-during-alias',
    'continued-public-flow', 'complete-state-policy-SRAM-and-drain')


def coverage_model():
    return CoverGroupDef('integrated_high_index_useful', (
        CoverPointDef('contract', {name: Bin.values(name) for name in HIGH_INDEX_CONTRACTS}),
    )).instantiate('kunminghu_v3.bpu.integrated_high_index_useful')


async def check_high_index(agent, output):
    plan = program()
    alias = base_alias(plan)
    checker = NonzeroChecks(dict(scope='integrated high-index / low-tag lower useful transitions'))
    observation = NonzeroObservation(agent, checker)
    report = dict(program=plan, hardware_internal_state_written=False, metadata_fabricated=False,
        full_FTQ_legality_proven=False)
    env = SparseProgramEnvironment(agent, checker, observation, report)

    async def until(predicate, label, limit=256):
        for _ in range(limit):
            checker.raise_failure()
            if predicate():
                return
            await env.wait(observation.settle(1), label, 8)
        raise AssertionError(dict(point=label, limit=limit, recent_writes=checker.bypass.writes[-4:]))

    async def qualified_return(value, phase, after_tick):
        context = value[phase][value['pc']]
        boundary = after_tick
        for _ in range(32):
            actual = await env.wait(agent.next_transaction(start_pc=value['pc'], after_tick=boundary, limit=256),
                'fresh high-index public lower readback', 512)
            boundary = actual.prediction_tick
            token = checker.bypass.index_tokens[boundary]
            physical = next(row['value']['hash_inputs'] for row in checker.bypass.records
                if row['phase'] == 'preedge' and row['tick'] == boundary - 1)
            if not qualifies_return_request(token, physical, program=value, after_tick=after_tick, phase=phase):
                continue
            source = next(row['abtb']['meta1'] for row in checker.records if row['tick'] == boundary)
            checker.compare(True, bool(conditional_source_ways(source, 6)), field='genuine_high_index_conditional_source')
            checker.compare(*training_tag_fold_pair(asdict(actual), context['tag_history']),
                field='high_index_public_training_folds_have_distinct_tag_ancestor')
            return actual, source, token
        raise AssertionError('no input-qualified high-index public lower return')

    async def check_negative_return(after_tick):
        context = plan['negative'][plan['pc']]
        lower = checker.bypass.references[0]
        expected = dict(data_valid=1, tag=208, position=6, counter=0)
        _, _, slot = lower.select(462)
        checker.compare(True, slot is not None, field='real_high_lower_resident_exists')
        checker.compare(expected, payload(lower.cells[slot]), field='planned_high_lower_counter_zero')
        actual, source, token = await qualified_return(plan, 'negative', after_tick)
        wanted, observed = public_readback_pair(asdict(actual), source, expected,
            pc=plan['pc'], index=context['indices'], position=6, target=plan['target'], table=0, prediction_position=10)
        checker.compare(wanted, observed, field='complete_high_index_lower_provider_public_return', input_token=token)
        return dict(transaction=asdict(actual), input_token=token, expected_payload=expected)

    try:
        await observation.__aenter__()
        await env.bootstrap(tuple(dict(pc=pc) for pc in sorted(set((*plan['nodes'], alias['nodes'][2])))))
        await env.prepare_returns(plan, 'high-index')
        alias_source = await env.install_return(alias['nodes'][2], alias['nodes'][3], 'alias return')
        await env.prepare(plan, 'high-index')
        returns = []
        for phase, goal in (('fallback', 0), ('positive', 3), ('negative', 0)):
            checker.phase = 'high-index-' + phase
            await env.steer(plan, goal)
            checkpoint = await env.steady_checkpoint(plan, taken=bool(goal), source='C')
            env.use_steady_source(plan, checkpoint, source='C')
            if phase == 'negative':
                def zero_lower():
                    reference = checker.bypass.references[0]
                    _, _, slot = reference.select(462)
                    return slot is not None and payload(reference.cells[slot]) == dict(
                        data_valid=1, tag=208, position=6, counter=0)
                await until(zero_lower, 'input-derived high lower counter reaches zero')
                # The goal can be reached after earlier A transactions were
                # already queued. Compare a request accepted AFTER that state,
                # not a stale pre-allocation miss from the checkpoint window.
                returns.append(await check_negative_return(checker.bypass.last_event.tick))
                old_source = checkpoint
            await env.stop('retire high-index phase ' + phase)

        # Steer the base through a genuine path alias, without changing the
        # trained original lower provider. No bank/set/slot sweep is involved.
        alias_begin = checker.bypass.last_event.tick
        protected_useful = checker.bypass.references[0].useful[462]
        await env.install_return(plan['nodes'][1], alias['nodes'][2], 'B to alias C')
        env.use_steady_source(alias, alias_source, source='C')
        checker.phase = 'high-index-base-alias-positive'
        await env.steer(alias, 3)
        alias_source = await env.steady_checkpoint(alias, source='C')
        env.use_steady_source(alias, alias_source, source='C')
        alias_context = alias['positive'][plan['pc']]
        base_index = physical_index(alias_context['index_pc'], alias_context['index_folds'][0])
        alias_actual, alias_abtb, alias_token = await qualified_return(alias, 'positive',
            checker.bypass.last_event.tick)
        checker.compare((1, 1 << (base_index % 4), base_index // 4),
            tuple(alias_abtb[key] for key in ('valid', 'bankMask', 'setIdx')),
            field='genuine_alias_uses_same_complete_ABTB_index')
        await until(lambda: any(row['phase'] == checker.phase and row['bank'] == base_index % 4
            and row['set_index'] == base_index // 4 and row['after'] == 3 and row['feedback'] is not None
            and row['feedback']['pc'] == plan['pc'] for row in checker.confirmed),
            'independently derived base-alias counter reaches taken saturation')
        await env.stop('retire base-alias positive flow')
        checker.phase = 'high-index-base-alias-negative-setup'
        await env.steer(alias, 0)
        await env.install_return(plan['nodes'][1], plan['nodes'][2], 'B to original C')
        env.use_steady_source(plan, old_source, source='C')
        alias_end = checker.bypass.last_event.tick
        checker.compare(protected_useful, checker.bypass.references[0].useful[462],
            field='original_useful_unchanged_during_base_alias')
        checker.phase = 'high-index-useful-increase'
        before_useful = checker.bypass.references[0].useful[462]
        await env.wait(agent.configure_predictors(abtb=True, settle=True), 'restore original fastTrain', 32)
        await env.capture(plan, 'original provider with oppositely biased base')
        await until(lambda: checker.bypass.references[0].useful[462] > before_useful,
            'original correct lower provider gains useful against wrong base')
        returns.append(await check_negative_return(checker.bypass.last_event.tick))
        await env.stop('retire useful increase and public readback')
        # Exercise the wrong-provider decrease only AFTER the gain. Taking this
        # direction first can allocate an upper provider that masks the lower
        # on return; that is a different semantic scenario, not extra latency.
        checker.phase = 'high-index-wrong-provider-decrease'
        before_useful = checker.bypass.references[0].useful[462]
        await env.steer(plan, 3)
        await until(lambda: checker.bypass.references[0].useful[462] < before_useful,
            'original wrong lower provider loses useful')
        await env.stop('retire complete high-index/base-alias scenario')
        checker.compare(0, len(checker.feedback_plans), field='all_high_index_genuine_feedback_observed')
        bypass, parent = checker.bypass.finish(), checker.summary()
        updates = collect_updates(checker.bypass.records)
        checker.compare([], [row for row in updates if alias_begin < row['tick'] <= alias_end],
            field='no_original_key_training_during_base_alias')
        roles = Counter(row['role'] for row in updates)
        checker.compare(set(HIGH_INDEX_ROLES), set(roles), field='all_required_high_useful_update_roles')
        checker.compare(True, any(row['role'] == 'increase' and row['after'] > row['before'] for row in updates),
            field='actual_high_useful_increase_not_only_saturation_hold')
        checker.compare(True, any(row['role'] == 'decrease' and row['after'] < row['before'] for row in updates),
            field='actual_high_useful_decrease_not_only_zero_hold')
        coverage = coverage_model()
        for contract in HIGH_INDEX_CONTRACTS:
            coverage.sample(dict(contract=contract))
        coverage.assert_coverage(100.0)
        write_functional_coverage(CoverageDatabase([coverage]), output / 'functional-coverage-high-index-useful.json')
        summary = dict(program=plan, base_alias=alias, alias_window=(alias_begin, alias_end),
            qualified_alias=dict(transaction=asdict(alias_actual), input_token=alias_token, base_index=base_index),
            public_returns=returns, update_roles=dict(roles),
            role_witnesses={role: next(row for row in updates if row['role'] == role) for role in HIGH_INDEX_ROLES},
            useful_updates_checked=len(updates), final_useful=checker.bypass.references[0].useful[462],
            checks=bypass, parent_checks=parent, passed=True, full_FTQ_legality_proven=False)
        # Do not serialize frame lists or the large full check summaries.
        (output / 'high-index-useful-summary.json').write_text(json.dumps({key: value for key, value in summary.items()
            if key not in ('checks', 'parent_checks')}, indent=2) + '\n')
        report.update(passed=True, summary=summary)
        return summary
    except BaseException as error:
        report['failure'] = repr(error)
        # Retain bounded semantic diagnostics, not the per-cycle frame stream.
        # A partially completed scenario earns no functional coverage credit.
        try:
            partial_updates = collect_updates(checker.bypass.records)
            partial_roles = Counter(row['role'] for row in partial_updates)
            update_diagnostics = dict(roles=dict(partial_roles),
                witnesses={role: next(row for row in partial_updates if row['role'] == role)
                    for role in partial_roles}, recent=partial_updates[-8:])
        except Exception as replay_error:
            update_diagnostics = dict(replay_failure=repr(replay_error))
        (output / 'high-index-useful-failure.json').write_text(json.dumps(dict(failure=repr(error),
            phase=checker.phase, recent_writes=checker.bypass.writes[-8:],
            checked_partial_updates=update_diagnostics,
            lower_shadow={key: checker.bypass.references[0].state()[key] for key in ('cells', 'status', 'enq', 'deq')},
            recent_A=[value for value in checker.coherent_transactions if value['prediction']['start_pc'] == plan['pc']][-2:]
            ), indent=2) + '\n')
        raise
    finally:
        await observation.aclose()
        report.update(bypass_records=checker.bypass.records, records=checker.records)
        dump_trace(output / 'integrated-high-index-useful.json', report)
