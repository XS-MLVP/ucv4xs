"""Synthetic corruption qualifies independent TAGE checking, not DUT coverage."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.checker.pipeline import PipelineChecker
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.pipeline import Events,Redirect
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from tests.bpu.scoreboard.test_direction_sources import learned,meta,ENABLED
from tests.bpu.scoreboard.test_main_ownership import input_bits,step
from tests.bpu.scoreboard.test_pipeline_checking import fixture_row


FIELDS=('hasProvider','hasAlt','useProvider','providerTableIdx','providerWayIdx',
    'providerTakenCtr_value','providerUsefulCtr_value','altOrBasePred','altConf')


def ready():
    model,event,anchor,token=learned()
    checker=PipelineChecker()
    checker.model=model
    checker.anchor=anchor
    checker.initialized,checker.last_tick=True,100
    checker.source_receipts[90]=token
    checker.s1_accepts[token.sequence]=86
    branch=token.early.branch
    entries=tuple(tuple(dict(rawHit=int(entry.hit),position=entry.position,
        attribute=dict(branchType=entry.kind,rasAction=entry.action),counter_value=entry.counter)
        for entry in row) for row in source_entries(token.lookup))
    tage=tuple({field:0 for field in FIELDS} for _ in range(4))
    for key,value in meta(model,token).items():
        slot,field=key.split('.')
        tage[int(slot)][field]=value
    source=NS(prediction_tick=86,meta_tick=90,prediction=NS(start_pc=token.pc,target=branch.target,
        taken=int(branch.taken),position=branch.position,s2_override=0,s3_override=0),
        meta=NS(perf=NS(start_pc=token.pc),redirect=dict(phr=token.history.metadata()),
            resolve=dict(phr=token.history.metadata(),mbtb_entries=entries,tage_entries=tage)))
    tx=BpuBatchTraining(token.pc,source.meta.resolve,(BpuBranchFeedback(4,token.pc+0x400,1,mispredict=1),))
    slot=next(int(key.split('.')[0]) for key in meta(model,token) if key.endswith('.providerTableIdx'))
    return checker,event,source,tx,slot


def state(checker):
    return deepcopy((checker.model.state(),checker.model.sources.main.state(),checker.model.sources.tage.state()))


@pytest.mark.parametrize('field',FIELDS)
@pytest.mark.parametrize('boundary',('receipt','accepted'))
def test_each_defined_tage_field_is_compared_without_advancing_or_repairing_golden(boundary,field):
    checker,event,source,tx,slot=ready()
    before=state(checker)
    if boundary=='receipt':
        source.meta.resolve['tage_entries'][slot][field]^=1
        with pytest.raises(AssertionError) as first:checker.plan_feedback(source,tx)
        assert not checker.feedback_plans
    else:
        checker.plan_feedback(source,tx)
        bits=input_bits(source,tx)
        bits['tage']=deepcopy(source.meta.resolve['tage_entries'])
        bits['tage'][slot][field]^=1
        with pytest.raises(AssertionError) as first:step(checker,event,training=bits)
        assert len(checker.feedback_plans)==1
    assert state(checker)==before and checker.last_resolution is None
    with pytest.raises(AssertionError) as second:checker.raise_failure()
    assert second.value is first.value


@pytest.mark.parametrize('field',FIELDS)
def test_public_s3_tage_corruption_prevents_new_receipt_and_model_advance(field):
    checker,event,source,_,_=ready()
    checker.source_token(source)
    origin=checker.anchor
    step(checker,replace(event,prediction_ready=False,
        redirect=Redirect(origin.history,origin.pc+4,origin.pc,True)))
    for _ in range(12):
        row=fixture_row(checker,event)
        cycle=checker.model.evaluate(event)
        values={} if cycle.metadata is None else checker.model.sources.defined_metadata(cycle.metadata)
        slots=[slot for slot in range(4) if f'{slot}.{field}' in values and f'{slot}.providerTableIdx' in values]
        if slots:
            row['observed']['metadata']['tage'][slots[0]][field]^=1
            before,receipts=state(checker),dict(checker.source_receipts)
            checker.capture(row,NS(tick=checker.last_tick+2))
            with pytest.raises(AssertionError):checker.raise_failure()
            assert state(checker)==before and checker.source_receipts==receipts
            return
        step(checker,event)
    raise AssertionError('synthetic provider-bearing publication not reached')


def test_correct_accepted_metadata_is_only_compared_never_used_as_model_input():
    checker,event,source,tx,_=ready()
    original=checker.source_token(source)
    event=replace(event,prediction_ready=False)
    for _ in range(4):step(checker,event)
    checker.plan_feedback(source,tx)
    bits=input_bits(source,tx)
    bits['tage']=source.meta.resolve['tage_entries']
    step(checker,event,training=bits)
    _,resolution=checker.last_resolution
    assert resolution.origin is original
    feedback=checker.model.sources.feedback_for(resolution)
    assert feedback.context==checker.model.sources.snapshot(original).read.context
    assert feedback.branches[0].hint.table==2 and feedback.branches[0].hint.counter==2


def test_undefined_provider_payload_is_not_treated_as_a_defined_match():
    checker,_,source,_,_=ready()
    absent=next(slot for slot in range(4) if not source.meta.resolve['tage_entries'][slot]['hasProvider'])
    for field in ('providerTableIdx','providerWayIdx','providerTakenCtr_value','providerUsefulCtr_value'):
        source.meta.resolve['tage_entries'][absent][field]=123
    assert checker.source_token(source) is checker.source_receipts[source.meta_tick]


def test_consumed_reset_controls_independent_clock_origin_not_newly_visible_reset_pin():
    checker,event,_,_,_=ready()
    # Real reset release has an additional consumed-reset boundary. No actual
    # random state or manually advanced PRNG enters this semantic event.
    checker.model.advance(replace(event,consumed_reset=True))
    assert checker.model.sources.tage.cycles==0
    assert checker.model.sources.tage.random==1
    checker.model.advance(replace(event,consumed_reset=False))
    assert checker.model.sources.tage.cycles==1 and checker.model.sources.tage.random==2


@pytest.mark.parametrize('value',(0,1,'reset',object()))
def test_consumed_reset_rejects_signal_level_or_nonsemantic_values(value):
    with pytest.raises(ValueError,match='consumed reset'):Events(0,consumed_reset=value)


def test_trained_tage_transition_rejects_live_older_work_instead_of_guessing_a_lookup():
    checker,event,_,_,_=ready()
    model=checker.model
    # The pipeline owns at least an older S2/S3 here; arbitrarily changing
    # enable without the documented drain cannot silently rebase its frame.
    for _ in range(5):
        if any(model.stages[1:]):break
        model.advance(event)
    assert any(model.stages[1:])
    disabled=replace(event,enabled=tuple(value if index!=3 else False for index,value in enumerate(ENABLED)))
    with pytest.raises(NotImplementedError,match='drained older'):
        for _ in range(4):model.advance(disabled)


def test_case_expresses_semantic_program_without_timing_or_embedded_checkers():
    tree=ast.parse(Path('bpu/case/direction_learning.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','create_task','Scoreboard'}
