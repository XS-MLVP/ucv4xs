"""Separate original eligibility from the lifetime of accepted learning."""
from concurrent.futures import Future
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import XEvent,XEventKind,XPhase,ScoreboardMismatch
from bpuverify.bpu.model.main_accepted_recovery import Program,FATES,MOMENTS,RULES
from bpuverify.bpu.coverage.main_accepted_recovery import Coverage
from bpuverify.bpu.checker.main_accepted_recovery import Checks
from bpuverify.bpu.model.window_lifetime import LifetimeError
from bpuverify.bpu.model.feedback_gate import wire_payload
from tests.bpu.scoreboard.test_feedback_gate import setup,source,prepare,accept,PROJECTION
from tests.bpu.scoreboard.test_partial_reuse import transfer

PROGRAMS=tuple(Program(f,m) for f in FATES for m in MOMENTS)


def event(tick):return XEvent(event_id=tick,tick=tick,phase=XPhase.RISING_STABLE,kind=XEventKind.CLOCK_RISE)


def new_checker(p):
    env=NS(checker=NS(last_tick=0,current_event=event(0),windows=NS(redirects=[]),raise_failure=lambda:None))
    c=Checks(env,p);c.close_when_retained=Future()
    c.request_recovery(NS(sequence=1 if p.cancelled else 2),NS(sequence=2))
    return c


def packet(c,*,training=False,proposal=False,retained=False,direction=False):
    p=c.program;d=dict(row=p.direction['row'],mask=p.direction['mask'],counters=[2,1])
    writes=[dict(valid=0,ready=0,bits={}) for _ in range(3)]
    if retained:
        writes[p.owner]=dict(valid=1,ready=0,bits=deepcopy(p.effect));writes[2]=dict(valid=1,ready=0,bits=d)
    incoming=[dict(valid=0,bits={}) for _ in range(2)]
    if proposal:incoming[p.owner]=dict(valid=1,bits=deepcopy(p.effect))
    dirty=[[0,0],[0,0]]
    if retained:dirty[p.owner][0]=1
    return dict(training=dict(valid=int(training),ready=1),incoming=incoming,
        direction=dict(valid=int(direction),ready=1,bits=d),writes=writes,dirty=dirty,
        read=dict(valid=1),queue=dict(enqueue=1,dequeue=0,full=0))


def capture(c,tick,row):
    c.env.checker.last_tick=tick;c.env.checker.current_event=event(tick)
    c.capture_state(event(tick),row)


def retained_checker(p):
    c=new_checker(p)
    capture(c,2,packet(c,training=True,direction=True))
    record=dict(tick=4 if p.moment=='publication-overlap' else 8,kind='external',
        owner=1 if p.cancelled else 2,discarded=(2,) if p.cancelled else ())
    if p.moment=='publication-overlap':c.env.checker.windows.redirects.append(record)
    capture(c,4,packet(c,proposal=True))
    capture(c,6,packet(c,retained=True))
    if p.moment=='retained-record':
        c.env.checker.windows.redirects.append(record);capture(c,8,packet(c,retained=True))
    assert c.close_when_retained.done()
    return c


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_accepted_copy_survives_recovery_even_when_its_prediction_is_no_longer_live(p):
    ledger,gate,older=setup();young=source(ledger,gate)
    tx=prepare(gate,young);teaching=accept(gate,tx).teaching;frozen=deepcopy(teaching)
    ledger.redirect(older if p.cancelled else young)
    assert (young in ledger.active)==(not p.cancelled)
    assert ledger.accepted==[teaching] and teaching.metadata==frozen.metadata and teaching.payload==frozen.payload
    assert gate.pending is None and ledger.cached is None and gate.accepts==1
    if p.cancelled:
        with pytest.raises(LifetimeError,match='flushed'):prepare(gate,young)
        assert gate.accepts==1 and ledger.accepted==[teaching]


@pytest.mark.parametrize('launched',(False,True))
@pytest.mark.parametrize('reset',(False,True))
def test_not_yet_accepted_original_cannot_borrow_the_post_acceptance_survival_rule(launched,reset):
    ledger,gate,older=setup();young=source(ledger,gate);tx=prepare(gate,young)
    if launched:gate.admit(tx)
    if reset:ledger.reset()
    else:ledger.redirect(older)
    with pytest.raises(LifetimeError):
        if launched:gate.accept(deepcopy(wire_payload(tx)),projection=deepcopy(PROJECTION))
        else:gate.admit(tx)
    assert gate.accepts==0 and not ledger.accepted


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_full_retained_copy_and_actual_services_follow_the_declared_recovery_boundary(p):
    c=retained_checker(p)
    assert c.first_retained['tick']==6 and c.retained_witness
    c.write_accepted(p.owner,transfer(11,deepcopy(p.effect)))
    bits=dict(row=p.direction['row'],mask=p.direction['mask'],counters=[2,1])
    c.write_accepted(2,transfer(11,bits))
    assert c.complete() and c.board.status.failed==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_complete_coverage_only_credits_its_own_logical_profile_once(p):
    c=Coverage(p)
    for rule in RULES:c.reach(rule)
    c.finish();assert c.groups['checked'].coverage==25
    with pytest.raises(AssertionError):c.finish()


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_every_missing_input_recovery_service_or_consumer_keeps_checked_empty(p,missing):
    c=Coverage(p)
    for rule in RULES:
        if rule!=missing:c.reach(rule)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('damage',('wrong-entry','wrong-owner','wrong-direction','duplicate-input','wrong-source-fate','wrong-phase','premature-service','stale-direction-service','duplicate-entry-service'))
def test_wrong_actual_payload_source_fate_or_service_latches_first_error_without_recompare(p,damage):
    c=new_checker(p)
    with pytest.raises(ScoreboardMismatch) as first:
        if damage in ('wrong-entry','wrong-owner','wrong-direction','duplicate-input'):
            row=packet(c,training=True,direction=True,proposal=True)
            if damage=='wrong-entry':row['incoming'][p.owner]['bits']['tag']^=1
            elif damage=='wrong-owner':row['incoming'][1-p.owner],row['incoming'][p.owner]=row['incoming'][p.owner],row['incoming'][1-p.owner]
            elif damage=='wrong-direction':row['direction']['bits']['mask']^=3
            else:c.inputs.append(1)
            capture(c,2,row)
            c.env.checker.windows.redirects.append(dict(tick=4,kind='external',owner=c.recovery_owner,discarded=(2,) if p.cancelled else ()))
            capture(c,4,packet(c,retained=True))
        elif damage in ('wrong-source-fate','wrong-phase'):
            capture(c,2,packet(c,training=True,direction=True));capture(c,4,packet(c,proposal=True))
            if damage=='wrong-phase' and p.moment=='publication-overlap':capture(c,6,packet(c,retained=True))
            tick=8 if p.moment=='publication-overlap' else 5
            discarded=(() if p.cancelled else (2,)) if damage=='wrong-source-fate' else ((2,) if p.cancelled else ())
            c.env.checker.windows.redirects.append(dict(tick=tick,kind='external',owner=c.recovery_owner,discarded=discarded))
            capture(c,tick,packet(c,retained=True))
        elif damage=='premature-service':c.write_accepted(p.owner,transfer(3,deepcopy(p.effect)))
        else:
            c=retained_checker(p)
            if damage=='stale-direction-service':
                c.write_accepted(2,transfer(11,dict(row=p.direction['row'],mask=p.direction['mask'],counters=[1,1])))
            else:
                c.write_accepted(p.owner,transfer(11,deepcopy(p.effect)))
                c.write_accepted(p.owner,transfer(13,deepcopy(p.effect)))
    before=deepcopy(c.summary())
    with pytest.raises(ScoreboardMismatch) as second:c.complete()
    assert first.value is second.value and c.summary()==before


@pytest.mark.parametrize('fate,moment',(('slot0','publication-overlap'),('source-cancelled','wait3'),(True,'retained-record'),('source-preserved',False)))
def test_physical_coordinates_and_wait_counts_are_not_semantic_profiles(fate,moment):
    with pytest.raises(ValueError):Program(fate,moment)
