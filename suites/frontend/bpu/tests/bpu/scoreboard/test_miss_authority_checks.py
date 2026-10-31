"""Qualifiers and literal transport have different semantics; preserve both."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.bpu.model.main_service import observed_counter
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from suites.frontend.bpu.bpu.model.feedback_gate import FeedbackGate,wire_payload
from suites.frontend.bpu.bpu.model.window_lifetime import WindowLifetimes,LifetimeError
from suites.frontend.bpu.bpu.model.miss_authority import Program,FOREIGN_PC,STREAM_PC,RULES
from suites.frontend.bpu.bpu.checker.miss_authority import Checks
from suites.frontend.bpu.bpu.coverage.miss_authority import Coverage


def checks(program):return Checks(SimpleNamespace(checker=SimpleNamespace(current_event=None)),program)


@pytest.mark.parametrize('inactive',(0,1,2,3))
def test_inactive_counter_bits_are_not_falsely_compared_as_writes(inactive):
    p=Program(True,False)
    checks(p).check([p.direction],[observed_counter(dict(row=16,mask=4,counters=(inactive,inactive,2,inactive)))],
        'inactive lane payload has no SRAM write authority')


@pytest.mark.parametrize('fault',('spurious-unhit-update','extra-allocated-lane','wrong-row','wrong-initialization'))
def test_actual_masked_corruption_is_not_normalized_away(fault):
    p=Program(fault!='spurious-unhit-update',True)
    bits=dict(row=16,mask=4,counters=(0,0,2,3))
    if fault=='spurious-unhit-update':bits.update(mask=8,counters=(0,0,0,1))
    elif fault=='extra-allocated-lane':bits['mask']=12
    elif fault=='wrong-row':bits['row']=17
    else:bits['counters']=(0,0,3,0)
    with pytest.raises(ScoreboardMismatch):checks(p).check([] if p.direction is None else [p.direction],
        [observed_counter(bits)],'only original hit or actual new-owner initialization can write a direction')


def prepared():
    metadata=dict(mbtb_entries=((dict(rawHit=0,position=7,counter_value=2,
        attribute=dict(branchType=1,rasAction=0)),),),unchanged_predictor_payload={'wide':1<<70})
    projection=dict(history={'phrLowBits':0},main=((dict(hit=0,position=7,counter=2),),))
    ledger=WindowLifetimes(1);gate=FeedbackGate(ledger)
    original=ledger.admit(FOREIGN_PC,metadata=projection);gate.remember(original,metadata)
    tx=BpuBatchTraining(FOREIGN_PC,deepcopy(metadata),(BpuBranchFeedback(7,STREAM_PC,1,taken=1,mispredict=1),))
    return gate,original,tx,metadata,projection


def test_literal_unhit_payload_is_transported_without_granting_it_semantic_authority():
    gate,original,tx,metadata,projection=prepared()
    gate.prepare(original,tx,receipt_metadata=metadata);gate.admit(tx)
    result=gate.accept(deepcopy(wire_payload(tx)),projection=projection)
    assert result.source is original and gate.accepts==1
    assert tx.resolve_meta['mbtb_entries'][0][0]['position']==7


@pytest.mark.parametrize('field',('position','counter_value','branchType'))
@pytest.mark.parametrize('when',('before-prepare','before-launch','actual-input'))
def test_clearing_or_replacing_unhit_fields_is_still_illegal_transport_mutation(field,when):
    gate,original,tx,metadata,projection=prepared()
    if when!='before-prepare':gate.prepare(original,tx,receipt_metadata=metadata)
    if when=='actual-input':gate.admit(tx);packet=deepcopy(wire_payload(tx));target=packet['meta']['mbtb_entries'][0][0]
    else:target=tx.resolve_meta['mbtb_entries'][0][0]
    if field=='branchType':target['attribute'][field]=0
    else:target[field]=0
    with pytest.raises(LifetimeError):
        if when=='before-prepare':gate.prepare(original,tx,receipt_metadata=metadata)
        elif when=='before-launch':gate.admit(tx)
        else:gate.accept(packet,projection=projection)
    assert gate.accepts==0


@pytest.mark.parametrize('allocate',(False,True))
@pytest.mark.parametrize('same_position',(False,True))
@pytest.mark.parametrize('missing',RULES)
def test_any_missing_input_effect_or_consumer_obligation_blocks_checked_credit(allocate,same_position,missing):
    coverage=Coverage(Program(allocate,same_position))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('allocate',(False,True))
@pytest.mark.parametrize('same_position',(False,True))
def test_only_complete_correct_case_gets_its_own_checked_combination_once(allocate,same_position):
    coverage=Coverage(Program(allocate,same_position))
    for rule in RULES:coverage.reach(rule)
    coverage.finish();assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])


@pytest.mark.parametrize('allocate,same',((0,True),(True,1),(None,False),(True,None)))
def test_ambiguous_semantic_modes_are_rejected(allocate,same):
    with pytest.raises(ValueError):Program(allocate,same)
