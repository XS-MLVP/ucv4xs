"""Synthetic event/fault contracts, never native DUT reachability evidence."""
from copy import deepcopy
import pytest
from toffee import ScoreboardMismatch, CoverageDatabase
from bpuverify.bpu.coverage.ras_micro import MicroRasEvents, micro_coverage, RULES
from bpuverify.bpu.model.ras.micro_events import pending_interaction
from bpuverify.bpu.checker.ras.micro import MicroRasChecker
from bpuverify.uras.model.pipeline import empty_state
from tests.bpu.scoreboard.test_early_ras import inputs


def row(checker,operation,reset=0):
    return dict(reset=reset,state=deepcopy(checker.expected),inputs=operation,
        output={name:checker.expected[name] for name in ('usable','address')})


def prepared(rule):
    coverage=MicroRasEvents();checker=MicroRasChecker(coverage=coverage)
    checker.observe(row(checker,inputs(),reset=1),1)
    for tick,pc in ((3,0x800),(5,0x900),(7,0xa00)):
        checker.observe(row(checker,inputs(2,s1=dict(pc=pc,position=15,action=2))),tick)
    tick=9
    if rule=='return-pairs-S3-uses-main':
        checker.observe(row(checker,inputs(0)),tick);tick+=2
    action=1 if rule.endswith('RETURN') or rule.startswith('return-') else 2
    operation=inputs(action)
    if rule.startswith('neutral-'):
        operation['s2'].update(valid=1,action=0)
    event_row=row(checker,operation)
    checker.observe(event_row,tick)
    assert coverage.pending['rule']==rule
    assert coverage.reached.samples==1 and coverage.checked.samples==0
    return checker,coverage,tick


@pytest.mark.parametrize('rule',RULES)
def test_credit_requires_following_full_state_and_output_comparison(rule):
    checker,coverage,tick=prepared(rule)
    checker.observe(row(checker,inputs(fire1=0)),tick+2)
    coverage.require(rule,tick,check=checker.check)
    assert coverage.reached.samples==coverage.checked.samples==1
    assert coverage.summary()['counts']==dict(reached=1,checked=1)


@pytest.mark.parametrize('fault',(*empty_state(),'output-usable','output-address','late-tick'))
def test_effect_fault_keeps_reached_event_and_contextual_failure(tmp_path,fault):
    checker,coverage,tick=prepared('neutral-S2-cancel-S1-RETURN')
    following=row(checker,inputs(fire1=0))
    if fault.startswith('output-'):following['output'][fault[7:]]^=1
    elif fault!='late-tick':following['state'][fault]^=1
    with pytest.raises(ScoreboardMismatch):
        checker.observe(following,tick+(4 if fault=='late-tick' else 2))
    assert coverage.summary()['counts']==dict(reached=1,failed=1)
    assert coverage.checked.samples==0
    assert 'failure' in coverage.recent[-1]
    coverage.write(tmp_path,'failure')
    database=CoverageDatabase.read_json(tmp_path/'functional-coverage-micro-ras-events-failure.json')
    assert database.groups[coverage.reached.instance].samples==1
    assert database.groups[coverage.checked.instance].samples==0


@pytest.mark.parametrize('fault',('reset','redirect','older-S3-correction','neutral-no-fire2',
    'neutral-not-neutral','neutral-no-fire1','neutral-younger-none','no-older-push',
    'return-no-fire1','return-younger-call','return-S2-pop','return-no-older-push'))
def test_presentation_without_required_qualifiers_does_not_create_event(fault):
    state=dict(empty_state(),s3_push=1,s3_address=0x600)
    operation=inputs(1);reset=0
    if fault.startswith('neutral-') or fault in ('reset','redirect','older-S3-correction','no-older-push'):
        operation['s2']['valid']=1
    if fault=='reset':reset=1
    elif fault=='redirect':operation['redirect']=1
    elif fault=='older-S3-correction':operation['s3']['valid']=1
    elif fault=='neutral-no-fire2':operation['fire2']=0
    elif fault=='neutral-not-neutral':operation['s2']['action']=2
    elif fault=='neutral-no-fire1':operation['fire1']=0
    elif fault=='neutral-younger-none':operation['s1']['action']=0
    elif fault in ('no-older-push','return-no-older-push'):state['s3_push']=0
    elif fault=='return-no-fire1':operation['fire1']=0
    elif fault=='return-younger-call':operation['s1']['action']=2
    elif fault=='return-S2-pop':state['s2_pop']=1
    assert pending_interaction(state,operation,reset) is None


def test_program_witness_cannot_use_another_event_tick_or_rule():
    checker,coverage,tick=prepared('neutral-S2-cancel-S1-CALL')
    with pytest.raises(ScoreboardMismatch,match='exact associated'):
        coverage.require('neutral-S2-cancel-S1-CALL',tick,check=checker.check)
    checker.observe(row(checker,inputs(fire1=0)),tick+2)
    for rule,event_tick in (('neutral-S2-cancel-S1-RETURN',tick),('neutral-S2-cancel-S1-CALL',tick+2)):
        with pytest.raises(ScoreboardMismatch,match='exact associated'):
            coverage.require(rule,event_tick,check=checker.check)


def test_all_interaction_bins_need_independently_checked_events():
    reached,checked=micro_coverage('reached'),micro_coverage('checked')
    for rule in RULES:
        checker,coverage,tick=prepared(rule)
        checker.observe(row(checker,inputs(fire1=0)),tick+2)
        reached.merge(coverage.reached);checked.merge(coverage.checked)
    reached.assert_coverage(100);checked.assert_coverage(100)


def test_failure_latched_by_monitor_callback_preserves_event_status():
    from types import SimpleNamespace
    checker,coverage,tick=prepared('return-pairs-S2-forwards-S3')
    following=row(checker,inputs(fire1=0));following['state']['address']^=1
    checker.capture(SimpleNamespace(value=following,event=SimpleNamespace(tick=tick+2)))
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert coverage.counts['failed']==1 and coverage.checked.samples==0
