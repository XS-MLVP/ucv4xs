"""Retain an old conditional entry using sparse, genuine program traffic."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from copy import deepcopy
from dataclasses import asdict
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase, CrossDef

from suites.frontend.bpu.runtime.trace import dump_trace
from suites.frontend.bpu.bpu.case.bypass.public_readback import (
    conditional_source_ways, public_readback_pair, training_tag_fold_pair,
)
from suites.frontend.bpu.bpu.checker.bypass.index_scope import NonzeroChecks
from suites.frontend.bpu.bpu.coverage.bypass.selection import ResponseSelectionCoverage
from suites.frontend.bpu.bpu.env.bypass.index_scope import NonzeroObservation
from suites.frontend.bpu.bpu.env.bypass.sparse import SparseProgramEnvironment
from suites.frontend.bpu.bpu.model.bypass.model import payload
from suites.frontend.bpu.bpu.model.bypass.partial_wrap import filled_with, retained_fallback
from suites.frontend.bpu.bpu.model.bypass.sparse import recipe, qualifies_return_request


async def check_sparse_wrap(agent, output, *, survivor_slot=6):
    if type(survivor_slot) is not int or survivor_slot not in (1, 3, 4, 5, 6):
        raise ValueError('sparse wrap survivor must be slot1, slot3, slot4, slot5 or the original slot6')
    first_write_slot = survivor_slot + 1
    case = 'sparse-wrap' if survivor_slot == 6 else f'sparse-wrap-slot{survivor_slot}'
    feature = ('BPU-INT-064' if survivor_slot == 6 else
               None if survivor_slot == 1 else 'BPU-INT-065')
    plan = recipe()
    old, second = plan['old'], plan['second']
    checker = NonzeroChecks(dict(scope='sparse conditional old key above wrapped prefix'))
    observation = NonzeroObservation(agent, checker)
    report = dict(plan=plan, hardware_internal_state_written=False, metadata_fabricated=False,
                  full_FTQ_legality_proven=False)
    env = SparseProgramEnvironment(agent, checker, observation, report)
    old_context = old['negative'][old['pc']]
    index = old_context['indices'][1]
    expected = dict(data_valid=1, tag=old_context['tags'][1], position=old['position'], counter=0)

    async def until(predicate, label, limit=512):
        for _ in range(limit):
            checker.raise_failure()
            if predicate():
                return
            await env.wait(observation.settle(1), label, 8)
        upper = checker.bypass.references[1]
        raise AssertionError(dict(point=label, limit=limit,
            upper_reference={key: value for key, value in upper.state().items() if key != 'useful'},
            recent_writes=checker.bypass.writes[-4:]))

    async def prepare_resident(program, label):
        await env.prepare_returns(program, label)
        await env.prepare(program, label)
        for phase, goal in (('fallback', 0), ('positive', 3), ('negative', 0), ('positive_again', 3),
                            ('learn_negative_upper', 0)):
            checker.phase = label + '_' + phase
            await env.steer(program, goal)
            await env.steady_checkpoint(program, taken=bool(goal))
            if phase == 'positive_again':
                context = program['positive' if goal else 'negative'][program['pc']]
                lower_payload = dict(data_valid=1, tag=context['tags'][0],
                                     position=program['position'], counter=7 if goal else 0)
                await until(lambda: filled_with(checker.bypass.references[0], context['indices'][0], lower_payload),
                            label + '_' + phase + '_lower_direction_saturated')
        context = program['negative'][program['pc']]
        wanted = dict(data_valid=1, tag=context['tags'][1], position=program['position'], counter=0)
        await until(lambda: filled_with(checker.bypass.references[1], context['indices'][1], wanted),
                    label + '_all_upper_residents_saturated')
        return await env.steady_checkpoint(program, taken=False)

    try:
        await observation.__aenter__()
        await env.bootstrap(tuple(dict(pc=pc) for program in (old, second) for pc in program['nodes']))
        second_checkpoint = await prepare_resident(second, 'second')
        old_checkpoint = await prepare_resident(old, 'old')
        upper = checker.bypass.references[1]
        await env.stop('old sparse residents prepared')
        # The highest old survivor is immediately before the first new write.
        # Stop on input-derived enq and account for already accepted work.
        await env.align_upper_boundary(first_write_slot, until)
        checker.compare(first_write_slot, upper.enq % 8, field='sparse_old_first_wrap_start')
        checker.compare(True, filled_with(upper, index, expected), field='all_sparse_old_resident_payloads')
        expected_slot = (upper.enq - 1) % 8
        checker.compare(survivor_slot, expected_slot, field='input_planned_highest_old_survivor')
        report['old_shadow'] = deepcopy(upper.state())

        checker.phase = 'sparse_second_partial_wrap'
        await env.restore_steady(second, second_checkpoint)
        await env.wait(agent.set_ready(prediction=True, meta=True), 'accept second sparse ring', 8)
        if survivor_slot == 1:
            # Waiting for fallback itself is too late here: backpressure can
            # retire another accepted write into slot1. Stop BEFORE the wrap;
            # the already accepted sparse branch must form the one-bit prefix.
            await until(lambda: upper.enq % 8 == 0, 'pre-wrap stopping point for slot1 survivor')
        else:
            await until(lambda: retained_fallback(upper, index) is not None, 'sparse_partial_wrap_retains_old_key')
        await env.stop('stop second sparse ring before complete eviction')
        prepared = retained_fallback(upper, index)
        checker.compare(True, prepared is not None, field='sparse_survivor_preserved_after_all_accepted_work')
        checker.compare(expected_slot, prepared['slot'], field='sparse_predicted_highest_old_slot')
        checker.compare(expected, payload(upper.cells[prepared['slot']]), field='sparse_retained_complete_payload')
        report['partial_wrap'] = dict(prepared, tick=checker.bypass.last_event.tick)

        checker.phase = 'sparse_old_fallback_return'
        request_boundary = boundary = await env.restore_steady(old, old_checkpoint)
        await env.wait(agent.set_ready(prediction=True, meta=True), 'accept sparse old-key return', 8)
        checked_return = None
        for _ in range(32):
            actual = await env.wait(agent.next_transaction(start_pc=old['pc'], after_tick=boundary, limit=256),
                                    'associated sparse old public transaction', 512)
            boundary = actual.prediction_tick
            token = checker.bypass.index_tokens[actual.prediction_tick]
            physical = next(row['value']['hash_inputs'] for row in checker.bypass.records
                if row['phase'] == 'preedge' and row['tick'] == actual.prediction_tick - 1)
            if not qualifies_return_request(token, physical, program=old, after_tick=request_boundary, phase='negative'):
                continue
            source = next(row['abtb']['meta1'] for row in checker.records if row['tick'] == actual.prediction_tick)
            checker.compare(True, bool(conditional_source_ways(source, old['position'])),
                            field='sparse_old_installed_conditional_at_public_return')
            expected_folds, observed_folds = training_tag_fold_pair(asdict(actual), old_context['tag_history'])
            checker.compare(expected_folds, observed_folds,
                field='sparse_public_training_tag_context_has_exact_prior_S1_ancestry')
            wanted, observed = public_readback_pair(asdict(actual), source, expected,
                pc=old['pc'], index=old_context['indices'], position=old['position'], target=old['target'],
                prediction_position=old['fallback'])
            checker.compare(wanted, observed, field='sparse_associated_public_payload_and_prediction',
                            input_token=token, recovery_tick=request_boundary, hash_inputs=physical)
            checked_return = dict(transaction=asdict(actual), input_token=deepcopy(token), source_ABTB=source)
            break
        checker.compare(True, checked_return is not None, field='input_qualified_sparse_return_checked')
        report['old_return'] = checked_return
        await env.stop('complete sparse return and older fastTrain')
        checker.compare(0, len(checker.feedback_plans), field='all_sparse_feedback_observed')
        report.update(passed=True, ABTB_summary=checker.summary(), bypass_summary=checker.bypass.finish(),
                      bypass_records=checker.bypass.records)
        selection = ResponseSelectionCoverage()
        result = selection.collect(report, required=((1, expected_slot, 'fallback'),),
                                   required_after_tick=checked_return['input_token']['source_tick'])
        checker.compare(checked_return['input_token']['source_tick'] + 1,
            result['required_witnesses'][0]['tick'], field='sparse_fallback_is_this_accepted_request_response')
        checker.compare(dict(hit=1, **expected), result['required_witnesses'][0]['expected'],
                        field='sparse_required_fallback_returns_old_complete_payload')
        preparation_keys = tuple(f'table0.slot{slot}.fallback' for slot in (1, 2, 7))
        for key in preparation_keys:
            checker.compare(True, result['occurrences'].get(key, 0) > 0,
                            field='required_fully_replayed_sparse_preparation_response', response=key)
        contracts = ('real_four_node_residents', 'negative_upper_payload_saturated',
                     'survivor_after_drain', 'distinct_index_tag_ancestry', 'negative_selects_later_CFI',
                     'associated_upper_slot6_fallback', 'lower_slot1_fallback',
                     'lower_slot2_fallback', 'lower_slot7_fallback')
        if survivor_slot == 6:
            # Preserve the published original schema and all its requirements.
            coverage = CoverGroupDef('integrated_sparse_shadow_wrap', (
                CoverPointDef('contract', {name: Bin.values(name) for name in contracts}),
            )).instantiate('kunminghu_v3.bpu.integrated_sparse_shadow_wrap')
        elif survivor_slot == 1:
            contracts = tuple('associated_planned_upper_fallback' if name == 'associated_upper_slot6_fallback'
                              else name for name in contracts)
            coverage = CoverGroupDef('integrated_sparse_slot1_return', (
                CoverPointDef('contract', {name: Bin.values(name) for name in contracts}),
            )).instantiate('kunminghu_v3.bpu.integrated_sparse_slot1_return')
        else:
            contracts = tuple('associated_planned_upper_fallback' if name == 'associated_upper_slot6_fallback'
                              else name for name in contracts)
            coverage = CoverGroupDef('integrated_sparse_wrap_boundaries', (
                CoverPointDef('survivor', {str(slot): Bin.values(slot) for slot in (3, 4, 5)}),
                CoverPointDef('contract', {name: Bin.values(name) for name in contracts}),
            ), crosses=(CrossDef('all_boundaries', ('survivor', 'contract')),)
            ).instantiate('kunminghu_v3.bpu.integrated_sparse_wrap_boundaries')
        for name in contracts:
            values = dict(contract=name)
            if survivor_slot in (3, 4, 5):
                values['survivor'] = survivor_slot
            coverage.sample(values)
        selection.save(output, case=case)
        write_functional_coverage(CoverageDatabase([coverage]), output / f'functional-coverage-{case}.json')
        (output / f'{case}-summary.json').write_text(json.dumps(dict(
            feature=feature, planned_survivor=survivor_slot,
            boundary_alignment=report.get('boundary_alignment', []),
            partial_wrap=report['partial_wrap'], old_return=checked_return,
            required_after_tick=result['required_after_tick'], required_witnesses=result['required_witnesses'],
            required_preparation=preparation_keys, occurrences=result['occurrences'], passed=True), indent=2) + '\n')
        return result
    except BaseException as error:
        report['failure'] = repr(error)
        # Only bounded semantic diagnostics on failure, never a cycle trace.
        recent = [row for row in checker.coherent_transactions
                  if row['prediction']['start_pc'] in (old['pc'], second['pc'])][-2:]
        selected_ticks = {row['prediction_tick'] + offset for row in recent for offset in range(-5, 3)}
        failed = checker.bypass.failed_frame
        native_failure = None if failed is None else dict(phase=failed['phase'], tick=failed['tick'], tables=[
            dict(table=table, inputs=row['inputs'],
                expected={key: reference.state()[key] for key in ('enq', 'deq', 'mask', 'cells', 'status')},
                actual={key: row['state'][key] for key in ('enq', 'deq', 'mask', 'cells', 'status')},
                outputs=row['outputs'], sram_banks=failed['value']['sram'][table]['banks'])
            for table, (reference, row) in enumerate(zip(checker.bypass.references, failed['value']['tables'], strict=True))])
        (output / f'{case}-failure.json').write_text(json.dumps(dict(
            failure=repr(error), phase=checker.phase, planned_survivor=survivor_slot, recent_A=recent,
            boundary_alignment=report.get('boundary_alignment', []),
            partial_wrap=report.get('partial_wrap'),
            independently_checked_old_return=report.get('old_return'), failed_transition=native_failure,
            hash_context=[dict(tick=row['tick'], **row['value']['hash_inputs']) for row in checker.bypass.records
                          if row['phase'] == 'preedge' and row['tick'] in selected_ticks],
            recent_writes=checker.bypass.writes[-4:]), indent=2) + '\n')
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records, preedge_records=checker.control_records,
                      bypass_records=checker.bypass.records, bypass_writes=checker.bypass.writes)
        dump_trace(output / f'integrated-{case}.json', report)
