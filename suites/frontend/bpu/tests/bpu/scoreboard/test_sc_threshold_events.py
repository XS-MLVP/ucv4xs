"""Pure event contracts; synthetic samples never claim native reachability."""
import pytest
from toffee import Scoreboard, ScoreboardMismatch, CoverageDatabase, CheckContext, ScoreboardMode
from bpuverify.bpu.coverage.sc.bounds import ThresholdCoverage, RULES
from bpuverify.bpu.model.sc.bounds import threshold_events
from bpuverify.bpu.model.sc.used import threshold_update, MINIMUM, MAXIMUM, INITIAL

CASES=(
    ('increase-interior',INITIAL,(1,)),
    ('decrease-interior',INITIAL,(-1,)),
    ('enter-lower',MINIMUM+1,(-1,)),
    ('enter-upper',MAXIMUM-1,(1,)),
    ('leave-lower',MINIMUM,(1,)),
    ('leave-upper',MAXIMUM,(-1,)),
    ('reject-below-from-interior',MINIMUM+1,(-1,-1)),
    ('reject-above-from-interior',MAXIMUM-1,(1,1)),
    ('reject-below-at-bound',MINIMUM,(-1,)),
    ('reject-above-at-bound',MAXIMUM,(1,)),
    ('cancel-interior',INITIAL,(-1,1)),
    ('cancel-at-lower',MINIMUM,(-1,1)),
    ('cancel-at-upper',MAXIMUM,(1,-1)),
)


def update(way,value,directions):
    before=[INITIAL]*4
    before[way]=value
    return threshold_update(before,[dict(way=way,counter_update=True,threshold_delta=d) for d in directions])


def comparisons():
    board=Scoreboard('sc.threshold_event_contract')
    return lambda expected,actual,**details:board.check(expected=expected,actual=actual,
        context=CheckContext(scoreboard=board.name,mode=ScoreboardMode.DIRECT,request=details))


@pytest.mark.parametrize('way',range(4))
@pytest.mark.parametrize('rule,value,directions',CASES)
def test_event_is_classified_from_qualified_votes_and_prestate_not_test_label(way,rule,value,directions):
    transition=update(way,value,directions)
    event,=threshold_events(transition)
    assert event==dict(way=way,rule=rule,before=value,after=transition['after'][way],
        increments=directions.count(1),decrements=directions.count(-1),candidate=value+sum(directions))
    coverage=ThresholdCoverage()
    coverage.reach(transition,accepted_tick=11,controls_tick=12)
    assert coverage.reached.samples==1 and coverage.checked.samples==0
    coverage.confirm(13,list(transition['after']),check=comparisons())
    assert coverage.checked_rules[way,rule]==1
    assert coverage.summary()['counts']==dict(reached=1,checked=1)


@pytest.mark.parametrize('fault',('missing-effect','other-lane-corrupt','wrong-commit-tick'))
def test_failed_commit_keeps_reached_event_but_never_gains_checked_credit(tmp_path,fault):
    coverage=ThresholdCoverage();transition=update(2,MINIMUM,(-1,1))
    coverage.reach(transition,accepted_tick=11,controls_tick=12)
    actual=list(transition['after']);tick=13
    if fault=='missing-effect':actual[2]+=1  # Sequential per-vote boundary filtering would do this.
    elif fault=='other-lane-corrupt':actual[0]+=1
    else:tick+=2
    with pytest.raises(ScoreboardMismatch):coverage.confirm(tick,actual,check=comparisons())
    assert coverage.summary()['counts']==dict(reached=1,failed=1)
    assert coverage.reached.samples==1 and coverage.checked.samples==0
    assert coverage.recent[-1]['status']=='failed' and 'failure' in coverage.recent[-1]
    coverage.write(tmp_path,2,'lower')
    database=CoverageDatabase.read_json(tmp_path/'functional-coverage-sc-threshold-events-2-lower.json')
    assert database.groups[coverage.reached.instance].samples==1
    assert database.groups[coverage.checked.instance].samples==0


def test_reset_cancellation_does_not_claim_a_checked_update():
    coverage=ThresholdCoverage()
    coverage.reach(update(0,INITIAL,(1,)),accepted_tick=11,controls_tick=12)
    coverage.cancel(13)
    assert coverage.summary()['counts']==dict(reached=1,reset_cancelled=1)
    assert coverage.pending is None and coverage.checked.samples==0


@pytest.mark.parametrize('controls_tick',(10,11,13,14))
def test_no_event_credit_without_exact_source_association(controls_tick):
    coverage=ThresholdCoverage()
    with pytest.raises(AssertionError,match='actual acceptance'):
        coverage.reach(update(0,INITIAL,(1,)),accepted_tick=11,controls_tick=controls_tick)
    assert coverage.reached.samples==coverage.checked.samples==0


def test_an_unqualified_way_hold_is_not_a_qualified_cancellation():
    coverage=ThresholdCoverage()
    transition=update(0,INITIAL,())
    assert threshold_events(transition)==[]
    coverage.reach(transition,accepted_tick=11,controls_tick=12)
    assert coverage.pending is None and coverage.reached.samples==0
    with pytest.raises(AssertionError,match='incomplete checked threshold events'):
        coverage.require_bounds(0,'lower')


def test_actual_qualified_two_vote_zero_is_different_from_unqualified_hold():
    coverage=ThresholdCoverage()
    transition=update(0,MINIMUM,(-1,1))
    coverage.reach(transition,accepted_tick=11,controls_tick=12)
    with pytest.raises(AssertionError,match='unconfirmed'):
        coverage.reach(transition,accepted_tick=13,controls_tick=14)
    coverage.confirm(13,list(transition['after']),check=comparisons())
    assert coverage.checked_rules[0,'cancel-at-lower']==1


def test_all_52_event_bins_require_real_samples_not_a_list_of_rule_names():
    coverage=ThresholdCoverage()
    assert set(RULES)=={row[0] for row in CASES}
    for way in range(4):
        for index,(_,value,directions) in enumerate(CASES):
            transition=update(way,value,directions);accepted=2*index+1
            coverage.reach(transition,accepted_tick=accepted,controls_tick=accepted+1)
            coverage.confirm(accepted+2,list(transition['after']),check=comparisons())
        for side in ('lower','upper'):coverage.require_bounds(way,side)
    coverage.reached.assert_coverage(100)
    coverage.checked.assert_coverage(100)
    assert len(coverage.recent)==16
