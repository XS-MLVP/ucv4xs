"""Independent semantic derivation and whole-vector checker fault sensitivity."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.utage.model.saved_vector import PROGRAMS, OBLIGATIONS
from suites.frontend.bpu.utage.model.semantic import (Base, Context, Events, Feedback, Source,
    TRAIN_HISTORY_INDICES, UtageReference)
from suites.frontend.bpu.utage.transaction.types import UtagePrediction
from suites.frontend.bpu.utage.checker.saved_vector import Checks
from suites.frontend.bpu.utage.coverage.saved_vector import Coverage


def event(program,read,match=None,*,override=None,feedback=None):
    match=read if match is None else match
    positions=program.positions()
    bases=tuple(Base() if p is None else Base(True,p,p==2,1) for p in positions)
    return Events(read_pc=read.pc,read_context=read.context,select=True,advance=True,
        pc=match.pc,context=match.context,positions=tuple(p or 0 for p in positions),bases=bases,
        override=override,override_pc=program.target.pc,override_context=Context.from_recent(program.history),feedback=feedback)


def query(model,program,profile,seed=None):
    e=event(program,profile)
    if seed is not None:
        e=replace(e,positions=tuple(p or 0 for p in program.positions(seed)),
            bases=tuple(Base() if p is None else Base(True,p,p==2,1) for p in program.positions(seed)))
    model.advance(e);model.advance(e)
    return model.prediction


def teaching(prediction,position,taken):
    frame=prediction.frame
    sources=tuple(Source(base.valid,base.position,provider is not None,provider or 0,
        0 if provider is None else frame.read.entries[provider].counter,
        False if provider is None else frame.read.entries[provider].counter>=4,base.taken)
        for base,provider in zip(prediction.bases,frame.providers(),strict=True))
    return Feedback(frame.pc,frame.context,frame.read.indices,sources,position,bool(taken),1)


def source(prediction):
    values=prediction.values()
    rows=[]
    for slot in range(4):
        rows.append(dict(valid=values.get(f'{slot}.valid',0),hit=values.get(f'{slot}.hit',0),
            cfiPosition=values.get(f'{slot}.position',0),baseTaken=values.get(f'{slot}.base',0),
            tableId=values.get(f'{slot}.provider',0),takenCtr_value=values.get(f'{slot}.counter',0)))
    hits=tuple(v.get('hit',0) for v in rows)
    takens=tuple(values.get(f'{slot}.taken',0) for slot in range(4))
    return UtagePrediction(hits[0],takens[0],dict(readIndex=prediction.frame.read.indices,
        abtbResult=rows,foldedPathHistForTrain_hist=[dict(foldedHist=v) for v in prediction.frame.context.folds]),hits,takens)


def derive(program):
    model=UtageReference()
    checks=Checks(program)
    for profile in program.profiles:
        for step in profile.setup:
            original=query(model,program,profile,step.seed_position)
            checks.vector(profile,source(original),step.sources,program.positions(step.seed_position))
            model.advance(Events(feedback=teaching(original,step.position,step.taken)))
            model.advance();model.advance()
            checks.learning(profile,step)
            assert tuple(v.get(i,0) for v in model.useful for i in range(512))==tuple(checks.protection)
            checks.vector(profile,source(query(model,program,profile)),step.after)
    teacher=query(model,program,program.target)
    feedback=teaching(teacher,15,0) if program.learning else None
    old,young,decoy=program.profiles
    model.advance(event(program,old,feedback=feedback))
    original_read=model.read
    model.advance(event(program,young,old))
    older=model.frame
    model.advance(event(program,decoy,young))
    younger=model.frame
    model.advance(event(program,decoy,decoy,override=program.stage))
    restored=model.prediction
    assert restored.frame.read.entries is (younger if program.stage=='s2' else older).read.entries
    assert older.read.entries is original_read.entries
    checks.vector(program.target,source(restored),program.target.prepared,history=program.history)
    if program.learning:checks.learning(program.target)
    for profile in program.profiles:
        checks.vector(profile,source(query(model,program,profile)),
            program.latest if profile.name==program.target.name else profile.prepared)
    assert tuple(v.get(i,0) for v in model.useful for i in range(512))==tuple(checks.protection)
    assert model.accepted_feedback==program.feedbacks
    assert (model.low_tick,model.high_tick)==(int(program.learning),)*2
    return restored


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_unchanged_semantic_model_derives_whole_saved_vector_and_current_learning(program):
    derive(program)


FAULTS=('short-borrowed-counter','long-borrowed-counter','provider-swap','wrong-read-age','wrong-matching-history','valid-hole')


@pytest.mark.parametrize('program',tuple(p for p in PROGRAMS if not p.retag),ids=lambda p:p.label)
@pytest.mark.parametrize('fault',FAULTS)
def test_mixed_age_vector_or_metadata_is_rejected(program,fault):
    actual=deepcopy(source(derive(program)))
    if fault in FAULTS[:2]:
        table=0 if fault==FAULTS[0] else 1
        row=next(v for v in actual.meta['abtbResult'] if v['valid'] and v['tableId']==table)
        row['takenCtr_value'] ^= 1
    elif fault=='provider-swap':
        next(v for v in actual.meta['abtbResult'] if v['valid'])['tableId'] ^= 1
    elif fault=='wrong-read-age':actual.meta['readIndex']=(19,19)
    elif fault=='wrong-matching-history':actual.meta['foldedPathHistForTrain_hist'][TRAIN_HISTORY_INDICES[0]]['foldedHist'] ^= 1
    else:actual.meta['abtbResult'][0]['valid']=1
    with pytest.raises(ScoreboardMismatch) as caught:
        Checks(program).vector(program.target,actual,program.target.prepared)
    assert caught.value.context.request['point']


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_failed_or_partial_recovery_cannot_gain_checked_credit(program):
    coverage=Coverage(program)
    for rule in program.rules[:-1]:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert not coverage.closed
    assert coverage.groups['checked'].coverage==0
    coverage.reach(program.rules[-1]);coverage.finish()
    assert coverage.groups['checked'].coverage==pytest.approx(100*len(program.rules)/len(OBLIGATIONS))
    with pytest.raises(ValueError):coverage.reach(program.rules[0])


def test_contract_is_semantic_and_programs_do_not_enumerate_storage():
    contract=json.loads((Path(__file__).resolve().parents[3]/'docs/saved-vector-contract.json').read_text())
    assert tuple(contract['rules'])==PROGRAMS[0].rules
    assert len(PROGRAMS)==16 and len(OBLIGATIONS)==176
    assert {p.pc for program in PROGRAMS for p in program.profiles}=={0x40000000}
    for program in PROGRAMS:
        assert all(0<v.counter<7 for v in program.target.prepared)
        assert len({p.indices for p in program.profiles})==3
        assert all(a.counter!=b.counter for a,b in zip(program.target.prepared,program.latest,strict=True))==program.learning
