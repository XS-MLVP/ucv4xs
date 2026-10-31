"""Synthetic adapter/fault contracts, not real DUT coverage evidence."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.ras.semantic import RasSemanticComponentChecker
from suites.frontend.bpu.bpu.coverage.ras_redo import RedoCoverage, RULES, redo_coverage
from suites.frontend.bpu.ras.model.semantic import Events, RasReference, Recovery, Retirement


ADDRESS = 0x80030020
PC = ADDRESS//2


def actuals(model):
    p = model.projection
    pointer = dict(flag=p['calls']//16,value=p['calls']%16)
    public = dict(top=p['top'],redirect_meta=dict(ssp=p['group'],sctr=p['repeat'],tosw=pointer),
                  commit_meta=dict(ssp=p['group'],tosw=dict(pointer)))
    retained = dict(head=model.committed_head,cells=[dict(address=f.address//2,counter=f.repeat)
        for f in model.committed])
    return public,retained


def step(checker,events=Events(),*,consumer=None):
    tick = 1 if checker.input_tick is None else checker.input_tick+2
    consumer = dict(valid=1,taken=1,pc=PC,target=checker.model.projection['top']) if consumer is None else consumer
    checker.capture_input(NS(tick=tick),events,consumer=consumer)
    public,retained = actuals(checker.model)
    checker.capture_output(NS(tick=tick+1),public,retained=retained,consumer=consumer)
    checker.raise_failure()
    return tick+1


def initialized(*,coverage=None):
    checker = RasSemanticComponentChecker(coverage=coverage,return_pc=PC)
    step(checker,Events(reset=True))
    step(checker,Events(2,ADDRESS))
    return checker


def source(checker,tick):
    p = checker.model.projection
    return NS(meta_tick=tick,meta=NS(perf=NS(start_pc=PC),redirect=dict(ras=dict(
        ssp=p['group'],sctr=p['repeat'],tosw=dict(flag=p['calls']//16,value=p['calls']%16)))))


@pytest.mark.parametrize('calls',(8,9))
def test_owned_compressed_program_rolls_back_real_younger_suffix_and_retires_returns(calls):
    model = RasReference()
    sources = []
    for _ in range(12):
        sources.append(dict(model.projection))
        model.advance(Events(2,ADDRESS))
        model.advance()
    for before in sources[:calls-1]:
        model.advance(Events(retirement=Retirement(before['group'],before['calls'],2)))
        model.advance()
    before = sources[calls-1]
    model.advance(Events(recovery=Recovery(before['group'],before['calls'],before['repeat'],2,ADDRESS)))
    model.advance()
    assert model.program.calls==calls
    assert model.projection==dict(top=PC,group=1 if calls==8 else 2,repeat=7 if calls==8 else 0,calls=calls)
    model.advance(Events(retirement=Retirement(before['group'],before['calls'],2)))
    model.advance()
    for index in range(2):
        before = dict(model.projection)
        assert before['top']==PC
        model.advance(Events(1))
        model.advance(Events(retirement=Retirement(before['group'],before['calls'],1)))
        model.advance()
        model.advance()
        assert model.projection==dict(top=PC,group=1,repeat=calls-index-2,calls=calls)
    assert model.committed_head==1
    assert model.committed[1].address==ADDRESS
    assert model.committed[1].repeat==calls-3
    assert model.retirements==calls+2


@pytest.mark.parametrize('field',('valid','taken','target','pc'))
def test_return_consumer_fault_latches_without_advancing_program_or_checked_credit(field):
    coverage = RedoCoverage(8)
    checker = initialized(coverage=coverage)
    before = deepcopy(checker.model.state())
    consumer = dict(valid=1,taken=1,target=PC,pc=PC)
    consumer[field] ^= 1
    checker.capture_input(NS(tick=5),Events(1),consumer=consumer)
    failure = checker.failure
    with pytest.raises(AssertionError) as caught:
        checker.raise_failure()
    assert caught.value is failure
    assert checker.model.state()==before
    checker.capture_input(NS(tick=7),Events(2,ADDRESS),consumer=consumer)
    checker.capture_output(NS(tick=8),actuals(checker.model)[0],retained=actuals(checker.model)[1])
    assert checker.failure is failure and checker.model.state()==before
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('top','group','repeat','calls','retained-head','retained-cell'))
def test_public_or_retained_fault_prevents_source_publication_and_effect_credit(field):
    coverage = RedoCoverage(8)
    checker = initialized(coverage=coverage)
    checker.capture_input(NS(tick=5),Events(),consumer=dict(valid=1,taken=1,pc=PC,target=PC))
    public,retained = actuals(checker.model)
    if field=='top':public['top'] ^= 1
    elif field=='group':public['redirect_meta']['ssp'] ^= 1
    elif field=='repeat':public['redirect_meta']['sctr'] ^= 1
    elif field=='calls':public['redirect_meta']['tosw']['value'] ^= 1
    elif field=='retained-head':retained['head'] ^= 1
    else:retained['cells'][7]['address'] ^= 1  # Not only the selected cell.
    ledger = tuple(checker.expected)
    checker.capture_output(NS(tick=6),public,retained=retained)
    with pytest.raises(AssertionError):checker.raise_failure()
    assert tuple(checker.expected)==ledger
    assert coverage.groups['checked'].coverage==0


def test_source_metadata_uses_only_real_exported_fields_at_exact_coherent_phase():
    checker = initialized()
    tick = step(checker)
    tx = source(checker,tick)
    assert 'topRetAddr' not in tx.meta.redirect['ras']
    assert checker.source_expected(tx)==dict(ssp=1,tosw=dict(flag=0,value=1))


@pytest.mark.parametrize('field',('tick','pc','group','repeat','calls'))
def test_wrong_source_or_metadata_never_realigns_to_nearby_same_pc(field):
    checker = initialized()
    tick = step(checker)
    tx = source(checker,tick)
    if field=='tick':tx.meta_tick += 1
    elif field=='pc':tx.meta.perf.start_pc ^= 1
    elif field=='group':tx.meta.redirect['ras']['ssp'] ^= 1
    elif field=='repeat':tx.meta.redirect['ras']['sctr'] ^= 1
    else:tx.meta.redirect['ras']['tosw']['value'] ^= 1
    before = deepcopy(checker.model.state())
    with pytest.raises(AssertionError):checker.source_expected(tx)
    assert checker.failure is not None
    assert checker.model.state()==before


def recovery_event(model,calls):
    for _ in range(calls+2):
        model.advance(Events(2,ADDRESS))
        model.advance()
    prefix = model.checkpoints[(1,calls-1,(calls-2)%8)]
    return Events(recovery=Recovery(*prefix.redirect_key(),2,ADDRESS))


@pytest.mark.parametrize('calls',(8,9))
def test_recovery_is_reached_at_accept_and_checked_only_at_registered_effect(calls):
    model,coverage = RasReference(),RedoCoverage(calls)
    event = recovery_event(model,calls)
    model.advance(event)
    coverage.accept(event,model,101)
    assert coverage.groups['reached'].coverage==pytest.approx(200/len(RULES[calls]))
    assert coverage.groups['checked'].coverage==0
    coverage.consume(102,model)
    assert coverage.groups['checked'].coverage==0
    model.advance()
    coverage.consume(104,model)
    assert coverage.groups['checked'].coverage==coverage.groups['reached'].coverage


def test_a_late_comparison_cannot_satisfy_a_missed_registered_effect():
    model,coverage = RasReference(),RedoCoverage(8)
    event = recovery_event(model,8)
    model.advance(event)
    coverage.accept(event,model,101)
    with pytest.raises(AssertionError,match='exact comparison'):coverage.consume(106,model)
    assert coverage.groups['checked'].coverage==0


def test_failed_effect_comparison_cannot_grant_checked_credit():
    coverage,checker = RedoCoverage(8),initialized()
    checker.boundary_coverage = coverage
    event = recovery_event(checker.model,8)
    step(checker,event)
    assert coverage.groups['reached'].coverage>0
    checker.capture_input(NS(tick=7),Events(),consumer=dict(valid=0,taken=0,pc=0,target=0))
    public,retained = actuals(checker.model)
    public['top'] ^= 1
    checker.capture_output(NS(tick=8),public,retained=retained)
    with pytest.raises(AssertionError):checker.raise_failure()
    assert coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError,match='no effect comparison'):coverage.finish()


@pytest.mark.parametrize('event',(
    Events(recovery=Recovery(1,7,6,0)),
    Events(recovery=Recovery(1,7,6,2,ADDRESS),enabled=False),
    Events(recovery=Recovery(1,7,6,2,ADDRESS)),
))
def test_disabled_wrong_action_or_unowned_recovery_has_no_coverage(event):
    coverage,model = RedoCoverage(8),RasReference()
    coverage.accept(event,model,1)
    coverage.consume(4,model)
    assert coverage.groups['reached'].coverage==coverage.groups['checked'].coverage==0


def test_repeat_return_coverage_uses_committed_program_after_adjacent_forwarding():
    model,coverage = RasReference(),RedoCoverage(9)
    for _ in range(9):
        before = dict(model.projection)
        model.advance(Events(2,ADDRESS))
        model.advance(Events(retirement=Retirement(before['group'],before['calls'],2)))
        model.advance()
    first = dict(model.projection)
    model.advance(Events(1))
    second = dict(model.projection)
    model.advance(Events(1))
    events = Events(retirement=Retirement(first['group'],first['calls'],1))
    model.advance(events)
    coverage.accept(events,model,101)
    events = Events(retirement=Retirement(second['group'],second['calls'],1))
    model.advance(events)
    coverage.accept(events,model,103)
    coverage.consume(104,model)
    model.advance()
    coverage.consume(106,model)
    report = coverage.groups['checked'].report()
    assert coverage.groups['checked'].coverage==pytest.approx(200/7)
    assert report['instance']==redo_coverage(9,'checked').instance


def test_duplicate_retirement_of_redone_call_is_not_coverage():
    model,coverage = RasReference(),RedoCoverage(8)
    event = recovery_event(model,8)
    model.advance(event)
    coverage.accept(event,model,101)
    model.advance()
    event = Events(retirement=Retirement(1,7,2))
    model.advance(event)
    coverage.accept(event,model,105)
    # Duplicate delivery is rejected even without advancing the model again.
    with pytest.raises(AssertionError,match='more than once'):coverage.accept(event,model,107)
    with pytest.raises(AssertionError,match='owned speculative source'):model.advance(event)


def test_reset_cancels_pending_boundary_checks():
    model,coverage = RasReference(),RedoCoverage(8)
    event = recovery_event(model,8)
    model.advance(event)
    coverage.accept(event,model,101)
    coverage.accept(Events(reset=True),model,103)
    coverage.consume(110,model)
    assert not coverage.pending and coverage.recovery_key is None
    assert coverage.groups['checked'].coverage==0


def test_deasserted_enable_cannot_make_an_ignored_recovery_a_checked_effect():
    model,coverage = RasReference(),RedoCoverage(8)
    event = recovery_event(model,8)
    model.advance(event)
    coverage.accept(event,model,101)
    model.advance(Events(enabled=False))
    with pytest.raises(AssertionError,match='no accepted registered effect'):coverage.consume(104,model)
    assert coverage.groups['checked'].coverage==0


def surviving_program():
    checker = RasSemanticComponentChecker(return_pc=PC)
    step(checker,Events(reset=True))
    for _ in range(8):
        before = dict(checker.model.projection)
        step(checker,Events(2,ADDRESS))
        step(checker,Events(retirement=Retirement(before['group'],before['calls'],2)))
        step(checker)
    for _ in range(2):
        before = dict(checker.model.projection)
        step(checker,Events(1))
        step(checker,Events(retirement=Retirement(before['group'],before['calls'],1)))
        step(checker)
        step(checker)
    return checker


def test_closed_form_survivor_compares_actuals_after_all_real_operations():
    checker,coverage = surviving_program(),RedoCoverage(8)
    checker.boundary_coverage = coverage
    checker.check_survivors(calls=8,returns=2,return_pc=PC)
    assert coverage.groups['reached'].coverage==coverage.groups['checked'].coverage==pytest.approx(100/6)


@pytest.mark.parametrize('fault',('top','group','repeat','retained-head','retained-address','retained-repeat'))
def test_closed_form_survivor_fault_preserves_first_exception(fault):
    coverage,checker = RedoCoverage(8),surviving_program()
    checker.boundary_coverage = coverage
    public,retained = actuals(checker.model)
    # Closed-form assertion must not merely compare a model against itself.
    if fault=='top':public['top'] ^= 1
    elif fault=='group':public['redirect_meta']['ssp'] ^= 1
    elif fault=='repeat':public['redirect_meta']['sctr'] ^= 1
    elif fault=='retained-head':retained['head'] ^= 1
    elif fault=='retained-address':retained['cells'][1]['address'] ^= 1
    else:retained['cells'][1]['counter'] ^= 1
    checker.last_actual = (public,retained,checker.input_tick+1)
    with pytest.raises(AssertionError):checker.check_survivors(calls=8,returns=2,return_pc=PC)
    assert checker.failure is not None and coverage.groups['checked'].coverage==0


def test_case_has_no_edge_wait_get_set_or_native_state_seed():
    tree = ast.parse(Path('bpu/case/ras/redo_unwind.py').read_text())
    forbidden = {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','GetInternalSignal'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            name = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in forbidden


def test_no_vacuous_semantic_success():
    with pytest.raises(AssertionError,match='genuine retirement'):initialized().finish()
    with pytest.raises(AssertionError):RedoCoverage(8).finish()
