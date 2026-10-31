"""Same-boundary ownership controls; no synthetic DUT coverage credit."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.model.main_coincident_recovery import Program,PROGRAMS,RULES
from suites.frontend.bpu.bpu.coverage.main_coincident_recovery import Coverage
from suites.frontend.bpu.bpu.checker.feedback_gate import FeedbackChecker
from suites.frontend.bpu.bpu.checker.window_lifetime import WindowPipelineChecker
from suites.frontend.bpu.bpu.model.main_sources import BranchTargetSources
from suites.frontend.bpu.bpu.model.feedback_gate import wire_payload
from suites.frontend.bpu.bpu.model.window_lifetime import LifetimeError
from tests.bpu.scoreboard.test_feedback_gate import setup,source,prepare,PROJECTION
from tests.bpu.scoreboard.test_main_accepted_recovery import new_checker,packet,capture
from tests.bpu.scoreboard.test_partial_reuse import transfer


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_semantic_same_boundary_acceptance_preserves_learning_before_cancelling_young_predictions(p):
    ledger,gate,older=setup();young=source(ledger,gate)
    tx=prepare(gate,young);gate.admit(tx)
    teaching=gate.accept(deepcopy(wire_payload(tx)),projection=deepcopy(PROJECTION)).teaching
    ledger.redirect(older if p.cancelled else young)
    assert ledger.accepted==[teaching] and (young in ledger.active)==(not p.cancelled)
    assert gate.accepts==1 and gate.pending is None
    if p.cancelled:
        with pytest.raises(LifetimeError,match='flushed'):prepare(gate,young)


@pytest.mark.parametrize('enabled',(False,True))
def test_same_boundary_input_contract_is_explicit_and_compares_the_whole_original(monkeypatch,enabled):
    ledger,gate,older=setup();young=source(ledger,gate)
    tx=prepare(gate,young);gate.admit(tx)
    token=NS(sequence=young.sequence,pc=young.pc)
    c=FeedbackChecker(sources=BranchTargetSources(),capacity=3,simultaneous_training_recovery=enabled)
    c.gate=gate;c.windows=NS(owner=lambda received:young)
    c.current_row=dict(inputs=dict(redirect=dict(valid=1)),complete_training=deepcopy(wire_payload(tx)))
    monkeypatch.setattr(WindowPipelineChecker,'_accepted_origin',lambda *args:token)
    if not enabled:
        with pytest.raises(NotImplementedError):c._accepted_origin(PROJECTION,NS(tick=2))
        assert not ledger.accepted and gate.pending is not None
    else:
        assert c._accepted_origin(PROJECTION,NS(tick=2)) is token
        ledger.redirect(older)
        assert len(ledger.accepted)==1 and c.actual_inputs==[dict(tick=2,source=young.sequence,
            pc=young.pc,complete_metadata_and_all_payload_fields_compared=True)]


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_actual_same_boundary_is_required_before_complete_services_and_checked_credit(p):
    c=new_checker(p)
    c.env.checker.windows.redirects.append(dict(tick=2,kind='external',
        owner=1 if p.cancelled else 2,discarded=(2,) if p.cancelled else ()))
    capture(c,2,packet(c,training=True,direction=True))
    capture(c,4,packet(c,proposal=True));capture(c,6,packet(c,retained=True))
    assert c.close_when_retained.done() and c.recovery['tick']==c.inputs[0]==2
    c.write_accepted(p.owner,transfer(9,deepcopy(p.effect)))
    c.write_accepted(4,transfer(9,dict(row=p.direction['row'],mask=p.direction['mask'],counters=[0,0,2,1])))
    assert c.complete()
    coverage=Coverage(p)
    for rule in RULES:coverage.reach(rule)
    coverage.finish();assert coverage.groups['checked'].coverage==12.5


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',('earlier','later','wrong-fate','duplicate-input','wrong-kind','wrong-target','wrong-owner'))
def test_wrong_actual_temporal_identity_or_full_entry_does_not_pass_as_same_boundary(p,fault):
    c=new_checker(p)
    with pytest.raises(ScoreboardMismatch):
        if fault=='duplicate-input':c.inputs.append(1)
        recovery_tick=4 if fault=='earlier' else 1 if fault=='later' else 2
        discarded=(() if p.cancelled else (2,)) if fault=='wrong-fate' else ((2,) if p.cancelled else ())
        if fault=='earlier':capture(c,2,packet(c,training=True,direction=True))
        c.env.checker.windows.redirects.append(dict(tick=recovery_tick,kind='external',
            owner=1 if p.cancelled else 2,discarded=discarded))
        row=packet(c,training=fault!='earlier',direction=fault!='earlier',proposal=True)
        if fault=='wrong-kind':row['incoming'][p.owner]['bits']['kind']^=1
        elif fault=='wrong-target':row['incoming'][p.owner]['bits']['offset']^=1
        elif fault=='wrong-owner':row['incoming'].reverse()
        capture(c,4 if fault=='earlier' else 2,row)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_missing_source_acceptance_recovery_service_or_fresh_consumer_cannot_create_checked(p,missing):
    c=Coverage(p)
    for rule in RULES:
        if rule!=missing:c.reach(rule)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('value',(None,1,'yes'))
def test_same_boundary_scope_cannot_be_enabled_by_a_truthy_non_boolean(value):
    with pytest.raises(TypeError):FeedbackChecker(sources=BranchTargetSources(),capacity=3,
        simultaneous_training_recovery=value)
