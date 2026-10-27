"""Event qualification and negative consumers; synthetic rows earn no DUT credit."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard

from bpuverify.bpu.checker.direction_learning import DirectionLearningChecks
from bpuverify.bpu.coverage.direction_learning import DirectionCoverage
from bpuverify.bpu.model.pipeline import Outcome,Resolution
from bpuverify.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_direction_sources import prepared,resolve,revisit,ENABLED


def fixture():
    model,event,anchor=prepared()
    pc=anchor.pc
    feedback=Resolution(anchor.history,pc,(Outcome(4,pc+0x400,Kind.CONDITIONAL,True,mispredict=True),),origin=anchor)
    resolve(model,event,anchor,True,wrong=True)
    later=revisit(model,event,anchor,pc)
    retired=[]
    pipeline=NS(board=Scoreboard('direction-event-contract'),raise_failure=lambda:None,
        source_receipts={6:anchor},last_resolution_controls=(10,ENABLED),model=model,
        source_token=lambda source:source.token,retire_source=retired.append,
        corrections_for_source=lambda _:((14,2),))
    checks=DirectionLearningChecks(pipeline,pc,4,pc+0x400,DirectionCoverage())
    source=NS(token=later,prediction_tick=12,meta_tick=16)
    return checks,(10,feedback),source,retired


@pytest.mark.parametrize('fault',('pc','position','target','kind','taken','mispredict','action',
    'origin','no-receipt','duplicate-receipt','wrong-controls','wrong-tick','wrong-order'))
def test_wrong_accepted_event_or_source_cannot_begin_a_learning_obligation(fault):
    checks,event,source,retired=fixture()
    tick,resolution=event
    if fault=='pc':resolution=NS(pc=resolution.pc+16,origin=resolution.origin,branches=resolution.branches)
    elif fault=='origin':resolution=replace(resolution,origin=None)
    elif fault=='no-receipt':checks.pipeline.source_receipts.clear()
    elif fault=='duplicate-receipt':checks.pipeline.source_receipts[8]=resolution.origin
    elif fault=='wrong-controls':checks.pipeline.last_resolution_controls=(10,(False,)*7)
    elif fault=='wrong-tick':tick+=2
    elif fault!='wrong-order':
        branch=resolution.branches[0]
        values={name:getattr(branch,name) for name in ('position','target','kind','taken','mispredict','action')}
        values[fault]=int(values[fault])^1
        resolution=NS(pc=resolution.pc,origin=resolution.origin,branches=(NS(**values),))
    with pytest.raises(AssertionError) as first:checks.accepted((tick,resolution),'short' if fault=='wrong-order' else 'main')
    assert checks.pending is None and not checks.steps and not retired
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


@pytest.mark.parametrize('fault',('missing-repair','extra-repair','wrong-stage','wrong-tick','old-consumer',
    'no-branch','wrong-counter','wrong-metadata','wrong-phase'))
def test_a_bad_effect_cannot_close_its_accepted_source_or_release_ownership(fault):
    checks,event,source,retired=fixture()
    checks.accepted(event,'main')
    if fault=='missing-repair':checks.pipeline.corrections_for_source=lambda _:()
    elif fault=='extra-repair':checks.pipeline.corrections_for_source=lambda _:((14,2),(16,3))
    elif fault=='wrong-stage':checks.pipeline.corrections_for_source=lambda _:((14,3),)
    elif fault=='wrong-tick':checks.pipeline.corrections_for_source=lambda _:((16,2),)
    elif fault=='old-consumer':source.prediction_tick=10
    elif fault in ('no-branch','wrong-counter'):
        frame=source.token.lookup
        banks=tuple(replace(bank,entries=tuple(replace(entry,kind=0) for entry in bank.entries))
            if fault=='no-branch' else replace(bank,counters=(0,)*len(bank.counters)) for bank in frame.banks)
        source.token=replace(source.token,lookup=replace(frame,banks=banks))
    elif fault=='wrong-metadata':
        original=checks.pipeline.model.sources.defined_metadata
        def wrong(token):
            values=original(token)
            for key in values:
                if key.endswith('.hasProvider'):values[key]=1
            return values
        checks.pipeline.model.sources.defined_metadata=wrong
    with pytest.raises(AssertionError) as first:checks.observed(source,'short' if fault=='wrong-phase' else 'main')
    assert checks.pending is not None and not checks.steps and not retired
    assert checks.coverage.groups['checked'].coverage==0
    with pytest.raises(AssertionError) as second:checks.finish()
    assert second.value is first.value


def test_first_effect_releases_only_its_old_owner_but_does_not_claim_complete_program():
    checks,event,source,retired=fixture()
    checks.accepted(event,'main')
    checks.observed(source,'main')
    assert retired==[6] and checks.pending is None and checks.steps==['main']
    # Main establishment is prerequisite, not a substitute for alternate/raw
    # learning. Merely reaching this consumer earns none of the six new rules.
    assert all(group.coverage==0 for group in checks.coverage.groups.values())
    with pytest.raises(AssertionError,match='six accepted'):checks.finish()
