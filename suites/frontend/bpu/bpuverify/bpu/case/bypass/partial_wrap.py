"""Two real programs: retain an old key above the wrapped priority prefix."""
from copy import deepcopy
from dataclasses import asdict
import json

from bpuverify.common.env.trace import dump_trace
from bpuverify.bpu.case.bypass.two_program_plan import recipe, full_tags
from bpuverify.bpu.case.bypass.public_readback import conditional_source_ways, public_readback_pair
from bpuverify.bpu.checker.bypass.index_scope import NonzeroChecks
from bpuverify.bpu.env.bypass.index_scope import NonzeroObservation
from bpuverify.bpu.env.bypass.program import ProgramEnvironment
from bpuverify.bpu.model.bypass.model import payload
from bpuverify.bpu.model.bypass.partial_wrap import filled_with, retained_fallback, qualifies_return_request
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.coverage.bypass.selection import ResponseSelectionCoverage


async def check_partial_wrap(agent, output):
    plan = recipe(1)  # One input geometry, not a bank/set enumeration.
    old, second = plan['old'], plan['second']
    checker = NonzeroChecks(dict(scope='retained old key above partial-wrap prefix'))
    observation = NonzeroObservation(agent, checker)
    report = dict(plan=plan, hardware_internal_state_written=False, metadata_fabricated=False,
                  full_FTQ_legality_proven=False)
    env = ProgramEnvironment(agent, checker, observation, report)
    index = old['expected_conditional_upper_index']
    expected = dict(data_valid=1, tag=full_tags(old['pc'], folds(old['conditional_history']))[1],
                    position=old['position'], counter=7)

    async def until(predicate, label, limit=256):
        # A cycle is the sampling unit. Completion is a model state condition;
        # limit is only a failure budget, not an empirical settling interval.
        for _ in range(limit):
            checker.raise_failure()
            if predicate():
                return
            await env.wait(observation.settle(1), label, 8)
        raise AssertionError(dict(point=label, limit=limit,
            upper_reference={key: value for key, value in checker.bypass.references[1].state().items()
                             if key != 'useful'}, recent_writes=checker.bypass.writes[-8:]))

    async def prepare_resident(program, label):
        await env.prepare(program, label)
        for phase, goal in (('fallback', 0), ('positive', 3), ('negative', 0), ('positive_again', 3)):
            checker.phase = label + '_' + phase
            await env.steer(program, goal)
            if goal == 3:
                await env.steady_checkpoint(program)
            else:
                await until(lambda: checker.reference.logical() & 8191 == program['fallback_history'] & 8191,
                            label + '_fallback_input_history')
        wanted = dict(data_valid=1, tag=full_tags(program['pc'], folds(program['conditional_history']))[1],
                      position=program['position'], counter=7)
        await until(lambda: filled_with(checker.bypass.references[1],
            program['expected_conditional_upper_index'], wanted), label + '_all_upper_residents_saturated')
        return await env.steady_checkpoint(program)

    try:
        await observation.__aenter__()
        await env.bootstrap((old, second))
        # Save a genuine second-program input context before creating the old
        # residents. Its <=12-bit hash history is preserved by public metadata.
        second_checkpoint = await prepare_resident(second, 'second')
        old_checkpoint = await prepare_resident(old, 'old')
        upper = checker.bypass.references[1]
        await until(lambda: filled_with(upper, index, expected), 'all_old_shadow_residents_saturated')
        old_checkpoint = await env.steady_checkpoint(old)
        await env.stop('old resident preparation complete')
        # Prepare the first-write-after-wrap boundary using real old-program
        # traffic. This readback contract does not require same-slot dirty
        # overwrite (a separately tracked RTL defect). Keep its full assertion
        # active; never mask/seed the status to bypass that defect.
        for _ in range(8):
            if upper.enq % 8 == 0:
                break
            accepted_before = len(checker.coherent_transactions)
            await env.wait(agent.refresh_stalled_prediction(), 'advance genuine old-loop input', 16)
            await env.wait(observation.drain(), 'retire bounded old-loop work', 32)
            checker.compare(1, len(checker.coherent_transactions) - accepted_before,
                            field='bounded_refresh_accepts_exactly_one_genuine_FTQ_token')
        checker.compare(0, upper.enq % 8, field='old_residents_end_at_first_wrap_boundary')
        report['old_shadow'] = deepcopy(upper.state())
        checker.compare(True, filled_with(upper, index, expected), field='complete_old_resident_payloads')
        # New-program writes first replace [enq..7], then wrap into [0..p].
        # Predict the highest survivor NOW, before sending second-program
        # traffic. It is not necessarily slot7 when the initial enq is nonzero.
        expected_slot = (upper.enq - 1) % 8
        checker.compare(True, expected_slot > 0, field='input_plan_leaves_nonzero_old_survivor')

        checker.phase = 'second_partial_wrap'
        await env.restore_steady(second, second_checkpoint)
        await env.wait(agent.set_ready(prediction=True, meta=True), 'accept second-program predictions', 8)
        await until(lambda: retained_fallback(upper, index) is not None, 'partial_wrap_retains_old_key')
        await env.stop('stop second program before full eviction')
        prepared = retained_fallback(upper, index)
        checker.compare(True, prepared is not None, field='partial_wrap_survives_accepted_younger_work')
        checker.compare(expected_slot, prepared['slot'], field='predicted_highest_old_slot_survives_partial_prefix')
        checker.compare(expected, payload(upper.cells[prepared['slot']]), field='retained_old_full_payload')
        report['partial_wrap'] = dict(prepared, tick=checker.bypass.last_event.tick)

        checker.phase = 'old_fallback_return'
        boundary = await env.restore_steady(old, old_checkpoint)
        request_boundary = boundary
        await env.wait(agent.set_ready(prediction=True, meta=True), 'accept old-key return', 8)
        checked_return = None
        for _ in range(32):
            actual = await env.wait(agent.next_transaction(start_pc=old['pc'], after_tick=boundary, limit=256),
                                    'associated old public transaction', 512)
            boundary = actual.prediction_tick
            token = checker.bypass.index_tokens[actual.prediction_tick]
            physical = next(row['value']['hash_inputs'] for row in checker.bypass.records
                if row['phase'] == 'preedge' and row['tick'] == actual.prediction_tick - 1)
            # Qualify only the independently advanced input token and redirect
            # guard. Never filter by actual provider, hit, counter or response.
            if not qualifies_return_request(token, physical, pc=old['pc'],
                    history=old['conditional_history'], after_tick=request_boundary):
                continue
            source = next(row['abtb']['meta1'] for row in checker.records
                          if row['tick'] == actual.prediction_tick)
            checker.compare(True, bool(conditional_source_ways(source, old['position'])),
                field='old_installed_conditional_present_at_public_return')
            wanted, observed = public_readback_pair(asdict(actual), source, expected,
                pc=old['pc'], index=index, position=old['position'])
            checker.compare(wanted, observed, field='associated_public_old_payload_and_prediction',
                            input_token=token, recovery_tick=request_boundary, hash_inputs=physical)
            checked_return = dict(transaction=asdict(actual), input_token=deepcopy(token), source_ABTB=source)
            break
        checker.compare(True, checked_return is not None, field='input_qualified_public_return_checked')
        report['old_return'] = checked_return
        await env.stop('complete return and older fastTrain')
        checker.compare(0, len(checker.feedback_plans), field='all_feedback_observed')
        report.update(passed=True, ABTB_summary=checker.summary(), bypass_summary=checker.bypass.finish(),
                      bypass_records=checker.bypass.records)
        selection = ResponseSelectionCoverage()
        result = selection.collect(report, required=((1, expected_slot, 'fallback'),),
                                   required_after_tick=checked_return['input_token']['source_tick'])
        checker.compare(checked_return['input_token']['source_tick'] + 1,
            result['required_witnesses'][0]['tick'], field='fallback_is_the_read_of_this_accepted_public_request')
        checker.compare(dict(hit=1, **expected), result['required_witnesses'][0]['expected'],
                        field='required_fallback_returns_this_old_payload_not_an_incidental_preparation_hit')
        selection.save(output, case='partial-wrap')
        # Bounded semantic witnesses, not a per-cycle trace or state audit.
        (output / 'partial-wrap-summary.json').write_text(json.dumps(dict(
            feature='BPU-INT-063', partial_wrap=report['partial_wrap'], old_return=checked_return,
            required_after_tick=result['required_after_tick'], required_witnesses=result['required_witnesses'],
            occurrences=result['occurrences'], passed=True), indent=2) + '\n')
        return result
    except BaseException as error:
        report['failure'] = repr(error)
        raise
    finally:
        await observation.aclose()
        report.update(records=checker.records, preedge_records=checker.control_records,
                      bypass_records=checker.bypass.records, bypass_writes=checker.bypass.writes)
        dump_trace(output / 'integrated-partial-wrap.json', report)
