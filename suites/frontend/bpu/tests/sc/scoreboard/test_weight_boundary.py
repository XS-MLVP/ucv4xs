"""Closed-form obligations, source ownership, and detectable boundary faults."""
from copy import deepcopy
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from bpuverify.sc.checker.boundary import ScBoundaryChecks
from bpuverify.sc.model.boundary import FAMILY_FIELDS, ScBoundaryProgram, expected_feedback, observed_feedback
from bpuverify.sc.model.semantic import Events, ScReference
from bpuverify.sc.model.threshold import ScThresholdModel
from bpuverify.sc.transaction.types import ScLookup
from tests.sc.scoreboard.test_semantic_model import lookup, feedback, settle, actual_metadata


def actual(expected):
    return SimpleNamespace(takens=expected['takens'], useds=expected['useds'],
        meta=dict(deepcopy(expected['meta']), debug=deepcopy(expected['families'])))


def source(program, number=1):
    return SimpleNamespace(sequence_id=number,
        request=ScLookup(program.pc, 0, 0, branches=program.layout),
        accepted_event=SimpleNamespace(tick=10), completed_event=SimpleNamespace(tick=12))


def test_closed_form_program_does_not_import_the_cycle_reference_or_signal_access():
    module = ast.parse(Path('bpuverify/sc/model/boundary.py').read_text())
    imports = [node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)]
    assert imports == ['bpuverify.common.model.configuration', 'dataclasses', 'bpuverify.sc.transaction.types']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(module))


@pytest.mark.parametrize('accepted,reverse', ((-1, 0), (34, 0), (1, 1), (33, 33)))
def test_boundary_progress_cannot_invent_extra_learning_or_premature_recovery(accepted, reverse):
    with pytest.raises(ValueError):
        ScBoundaryProgram(1).weight(accepted, reverse=reverse)


@pytest.mark.parametrize('direction', (0, 1))
def test_distinct_original_sources_reach_every_family_endpoint_and_exact_reverse(direction):
    program = ScBoundaryProgram(direction)
    model, thresholds = ScReference(), ScThresholdModel()
    sources = tuple(lookup(model, branches=program.layout) for _ in range(program.source_count))
    assert len({id(value) for value in sources}) == program.source_count
    checker = ScBoundaryChecks(program)
    for step, prediction in enumerate(sources, 1):
        intended = program.feedback(program.expected(0, thresholds.values)['meta'])
        assert thresholds.apply(intended).qualifying_slots == (0,)
        model.advance(Events(feedback=feedback(prediction, outcome=direction)))
        settle(model)
        current = lookup(model, branches=program.layout)
        checker.prediction(program.expected(program.weight(step), thresholds.values),
            SimpleNamespace(takens=current.directions, useds=current.used, meta=actual_metadata(current)), state=step)
        assert model.thresholds.values == thresholds.values
    bias_column = 19 if direction else 18
    assert tuple(row[4 if family < 7 else bias_column] for family, row in enumerate(current.read.weights)) == (program.endpoint,) * 8
    for step in range(1, program.reverse_steps + 1):
        intended = program.feedback(program.expected(program.weight(program.source_count, reverse=step-1),
                                                     thresholds.values)['meta'], reverse=True)
        assert thresholds.apply(intended).qualifying_slots == (0,)
        model.advance(Events(feedback=feedback(current, outcome=1-direction)))
        settle(model)
        current = lookup(model, branches=program.layout)
        checker.prediction(program.expected(program.weight(program.source_count, reverse=step), thresholds.values),
            SimpleNamespace(takens=current.directions, useds=current.used, meta=actual_metadata(current)), state=step)
        assert current.directions[0] == (1-direction if step == program.reverse_steps else direction)
    assert all(value.sums == (8,) * 10 for value in sources)


def test_old_fresh_correct_agreement_is_not_a_boundary_witness():
    model = ScReference()
    program = ScBoundaryProgram(1)
    current = lookup(model, branches=program.layout)
    for _ in range(82):
        model.advance(Events(feedback=feedback(current, outcome=1)))
        settle(model)
        current = lookup(model, branches=program.layout)
    assert current.sums[0] == 24  # Eight weights of1 after one strong correct feedback.
    update = ScThresholdModel(initial=model.thresholds.values).apply(feedback(current, outcome=1))
    assert not update.qualifying_slots
    # Three real wrong fresh feedbacks expose the false saturation claim.
    for _ in range(3):
        model.advance(Events(feedback=feedback(current, outcome=0)))
        settle(model)
        current = lookup(model, branches=program.layout)
    checker = ScBoundaryChecks(program)
    with pytest.raises(AssertionError):
        checker.prediction(program.expected(program.endpoint-3, model.thresholds.values),
            SimpleNamespace(takens=current.directions, useds=current.used, meta=actual_metadata(current)),
            state='stable old output was falsely treated as the endpoint')


@pytest.mark.parametrize('direction', (0, 1))
@pytest.mark.parametrize('fault', ('early-clamp', 'wrap', 'lost-reverse'))
def test_reverse_consumers_distinguish_wrong_boundary_effects(direction, fault):
    program = ScBoundaryProgram(direction)
    if fault == 'early-clamp':
        step = 31
        wrong = program.weight(program.source_count, reverse=step) + (-1 if direction else 1)
    elif fault == 'wrap':
        step, wrong = 0, -32 if direction else 31
    else:
        step = 32
        wrong = program.weight(program.source_count, reverse=31)
    wanted = program.expected(program.weight(program.source_count, reverse=step), (1130,) * 8)
    with pytest.raises(AssertionError) as caught:
        ScBoundaryChecks(program).prediction(wanted, actual(program.expected(wrong, (1130,) * 8)), state=fault)
    assert 'expected' in str(caught.value) and 'actual' in str(caught.value) and fault in str(caught.value)


@pytest.mark.parametrize('family', FAMILY_FIELDS)
def test_one_wrong_family_cannot_hide_behind_a_correct_total_direction(family):
    program = ScBoundaryProgram(1)
    wanted = program.expected(-1, (1130,) * 8)
    wrong = actual(wanted)
    wrong.meta['debug'][family] = (1, 1, 1, 1)
    with pytest.raises(AssertionError, match=family):
        ScBoundaryChecks(program).prediction(wanted, wrong, state='one family lost the final reverse vote')


def test_source_lifetime_is_distinct_single_use_and_immutable():
    program = ScBoundaryProgram(1)
    checker = ScBoundaryChecks(program)
    wanted = program.expected(0, (1130,) * 8)
    prediction = actual(wanted)
    number = checker.source(source(program), prediction, wanted, state='cold')
    real, intended = checker.feedback(number)
    real.meta['scPred'] = (0,) * 4
    assert intended.meta['scPred'] == prediction.meta['scPred'] == (1,) * 10
    checker.finish()
    with pytest.raises(AssertionError):
        checker.feedback(number)
    with pytest.raises(AssertionError):
        checker.source(source(program), prediction, wanted, state='duplicate source')
    with pytest.raises(AssertionError):
        checker.feedback(999)
    prediction.meta['scPred'] = (0,) * 4
    with pytest.raises(AssertionError):
        checker.finish()


def test_missing_feedback_cannot_finish_a_designated_source():
    program = ScBoundaryProgram(0)
    checker = ScBoundaryChecks(program)
    wanted = program.expected(0, (1130,) * 8)
    checker.source(source(program), actual(wanted), wanted, state='cold')
    with pytest.raises(AssertionError):
        checker.finish()


@pytest.mark.parametrize('tick', (11, 12))
def test_feedback_cannot_precede_or_share_its_original_response(tick):
    program = ScBoundaryProgram(1)
    checker = ScBoundaryChecks(program)
    wanted = program.expected(0, (1130,) * 8)
    number = checker.source(source(program), actual(wanted), wanted, state='cold')
    checker.feedback(number)
    with pytest.raises(AssertionError):
        checker.accepted(number, tick)
    checker.accepted(number, 13)


@pytest.mark.parametrize('fault', ('pc', 'not-completed', 'wrong-age'))
def test_unowned_or_unpublished_source_is_not_eligible_evidence(fault):
    program = ScBoundaryProgram(1)
    transfer = source(program)
    if fault == 'pc':
        transfer.request = ScLookup(program.pc+8, 0, 0, branches=program.layout)
    elif fault == 'not-completed':
        transfer.completed_event = None
    else:
        transfer.completed_event.tick = 8
    wanted = program.expected(0, (1130,) * 8)
    with pytest.raises(AssertionError):
        ScBoundaryChecks(program).source(transfer, actual(wanted), wanted, state=fault)


@pytest.mark.parametrize('fault', ('none', 'valid', 'ready', 'pc', 'history', 'metadata', 'owner', 'extra-branch'))
def test_complete_feedback_offer_is_compared_not_just_its_count(fault):
    program = ScBoundaryProgram(1)
    transaction = program.feedback(program.expected(0, (1130,) * 8)['meta'])
    expected = expected_feedback(transaction, branch_count=8, fold_count=3)
    bits = dict(start_pc=program.pc, common_hr_valid=1, global_history=0, backward=0, loop=0,
        path_history=({'foldedHist': 0},) * 3,
        sc_meta=deepcopy(transaction.meta), mbtb_meta=deepcopy(expected['mbtb_meta']),
        branches=deepcopy(expected['branches']))
    raw = dict(valid=1, ready=1, bits=bits)
    if fault in ('valid', 'ready'):
        raw[fault] = 0
    elif fault == 'pc': bits['start_pc'] += 8
    elif fault == 'history': bits['global_history'] = 1
    elif fault == 'metadata': bits['sc_meta']['useScPred'] = (1,) * 4
    elif fault == 'owner': bits['mbtb_meta'][0][0]['rawHit'] = 0
    elif fault == 'extra-branch': bits['branches'][1]['valid'] = 1
    checker = ScBoundaryChecks(program)
    if fault == 'none':
        checker.check(expected, observed_feedback(raw))
    else:
        with pytest.raises(AssertionError):
            checker.check(expected, observed_feedback(raw), request=fault)


@pytest.mark.parametrize('direction', (-1, 2, True))
def test_boundary_outcome_is_not_a_free_form_count(direction):
    with pytest.raises(ValueError):
        ScBoundaryProgram(direction)
