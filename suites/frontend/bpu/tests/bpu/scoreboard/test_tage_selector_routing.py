"""Logical routing and complete commit contracts; no DUT/native credit."""
from itertools import product
from types import SimpleNamespace
import pytest
from toffee import CoverageDatabase,ScoreboardMismatch
from bpuverify.bpu.coverage.tage.selector import SelectorRoutingCoverage
from bpuverify.bpu.checker.tage.selector import TageSelectorChecker
from tests.bpu.scoreboard.test_tage_selector import metadata,transaction,sample


def pending_route(table,confidence):
    coverage=SelectorRoutingCoverage();checker=TageSelectorChecker(routing=coverage)
    reset=sample(checker);reset['reset']=1;checker.observe(reset,10);checker.observe(sample(checker),12)
    tx=transaction(metadata(table=table,conf=confidence),taken=0)
    tx.resolve_meta['mbtb_entries'][0][0]['counter_value']=0 if confidence else 1
    source=SimpleNamespace(prediction_tick=6,meta_tick=8,meta=SimpleNamespace(resolve=tx.resolve_meta))
    checker.phase='exercise';checker.plan(tx,source)
    checker.observe(sample(checker,tx,fire=(1,1,0,0)),14)
    checker.observe(sample(checker,fire=(0,0,1,0)),16)
    t3=sample(checker,fire=(0,0,0,1));t3['votes'][0]=dict(valid=1,index=2*table+confidence,inc=1,dec=0)
    return checker,coverage,t3


@pytest.mark.parametrize('table,confidence',tuple(product(range(4),(0,1))))
def test_genuine_source_routes_one_vote_then_checks_complete_eight_register_commit(table,confidence):
    checker,coverage,t3=pending_route(table,confidence);checker.observe(t3,18)
    assert coverage.groups['reached'].samples==1 and coverage.groups['checked'].samples==0
    checker.observe(sample(checker),20)
    expected=[16]*8;expected[2*table+confidence]=17
    assert list(checker.summary()['selectors'])==expected
    assert coverage.groups['checked'].samples==1
    report=coverage.groups['checked'].report()
    witness=next(iter(report['points'][0]['provenance'][str(2*table+confidence)].values()))['first']
    assert (witness['prediction_tick'],witness['meta_tick'],witness['accepted_tick'],witness['committed_tick'])==(6,8,14,20)


@pytest.mark.parametrize('fault',('missing-T3','wrong-index','invalid-vote','wrong-direction','missing-effect','neighbor-effect'))
def test_route_or_commit_failure_retains_reached_but_never_checked(fault):
    checker,coverage,t3=pending_route(0,0)
    if fault in ('missing-effect','neighbor-effect'):
        checker.observe(t3,18);row=sample(checker);tick=20
        if fault=='missing-effect':row['selectors'][0]=16
        else:row['selectors'][1]+=1
    else:
        row=t3;tick=18
        if fault=='missing-T3':row['fire']=(0,0,0,0)
        elif fault=='wrong-index':row['votes'][0]['index']=1
        elif fault=='invalid-vote':row['votes'][0]['valid']=0
        else:row['votes'][0].update(inc=0,dec=1)
    checker.capture(SimpleNamespace(value=row,event=SimpleNamespace(tick=tick)))
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert coverage.groups['reached'].samples==1 and coverage.groups['checked'].samples==0


def test_all_partial_logical_routes_merge_without_bank_or_stage_axes():
    merged=CoverageDatabase()
    for table,confidence in product(range(4),(0,1)):
        checker,coverage,t3=pending_route(table,confidence)
        checker.observe(t3,18);checker.observe(sample(checker),20)
        merged.merge(CoverageDatabase(list(coverage.groups.values())))
    for group in merged.groups.values():
        group.assert_coverage(100)
        assert group.samples==8
        assert tuple(point.name for point in group.definition.points)==('index',)
        assert not group.definition.crosses
