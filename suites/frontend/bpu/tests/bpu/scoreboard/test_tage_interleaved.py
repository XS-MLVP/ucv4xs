"""Pure semantic programs and synthetic qualification faults, not DUT evidence."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.checker.tage.interleaved import InterleavedLearningChecker
from suites.frontend.bpu.bpu.coverage.tage.interleaved import InterleavedCoverage
from suites.frontend.bpu.bpu.model.selection import fallthrough
from suites.frontend.bpu.bpu.model.tage.interleaved import PC,TRACKED,UNTRACKED,RESOLVED,OWNERS,target,opposing_base_program,discovery_outcomes
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction
from suites.frontend.bpu.tage.model.semantic import Base,Branch,Context,Events,Feedback,Hint,decide
from tests.tage.scoreboard.test_semantic_model import actual_prediction,learn,lookup


def prepared():
    checker = InterleavedLearningChecker(InterleavedCoverage())
    checker.capture_input(NS(tick=0),Events(reset=True))
    model = checker.model
    for position,(table,way) in zip(TRACKED,OWNERS,strict=True):
        feedback = Feedback(PC,Context(),(Branch(position,False,1,True,True,2),))
        for _ in range(128):
            if model.allocation_at_next_accept(feedback)==(table,way):break
            model.advance()
        else:raise AssertionError('pure owned allocation forecast did not recur')
        learn(model,feedback)
        learn(model,Feedback(PC,Context(),(Branch(position,False,1,False,True,1,
            Hint(True,False,False,table,way,3,0,False,False)),)))
    source,repairs = receipt(checker,4)
    assert not repairs
    return checker,source


def receipt(checker,tick,*,position=None,after=False):
    positions = (6,4,14,10) if position is None else (position,6,14,10) if position<8 else (6,4,position,10)
    frame = lookup(checker.model,pc=PC,positions=positions)
    counters = tuple(2 if position==p or not after else checker.main_counters.get(p,1) for p in positions)
    bases = tuple(Base(True,p,value>=2,value in (0,3),1) for p,value in zip(positions,counters,strict=True))
    checker.events,checker.input_tick = Events(advance=True),tick-1
    wanted = decide(frame,bases,checker.model.selectors)
    actual = actual_prediction(wanted)
    extras = {name:tuple(wanted.get(f'{slot}.{field}',0) for slot in range(4)) for name,field in
        (('fast_valids','fast_valid'),('fast_takens','fast_taken'),('sc_counters','sc_counter'))}
    checker.capture_output(NS(tick=tick),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    branch = fallthrough(PC).branch
    main = [dict(rawHit=1,position=p,counter_value=value) for p,value in zip(positions,counters,strict=True)]
    source = NS(prediction_tick=tick,meta_tick=tick+4,prediction=BpuPrediction(PC,branch.target,0,branch.position,0,0),
        meta=NS(resolve=dict(tage_entries=deepcopy(actual.metas),mbtb_entries=(main[:2],main[2:]))))
    repairs = () if position is None else ((tick+2,BpuPrediction(PC,target(position),1,position,1,0)),)
    return source,repairs


def accept(checker,*,feedback=None,slots=None,tick=None):
    planned = checker.pending
    checker.capture_input(NS(tick=planned[1].meta_tick+1 if tick is None else tick),
        Events(feedback=planned[2] if feedback is None else feedback),
        resolve_slots=planned[3] if slots is None else slots)
    checker.raise_failure()
    for _ in range(7):checker.model.advance()


def learned():
    checker,before = prepared()
    checker.arm_learning(before)
    accept(checker)
    after,repairs = receipt(checker,14,after=True)
    checker.consume_learning(after,repairs)
    return checker,after


def test_four_owned_providers_and_all_untracked_later_discoveries_close_the_event_contract():
    checker,source = learned()
    assert checker.coverage.groups['checked'].coverage==pytest.approx(400/6)
    for number,position in enumerate(UNTRACKED):
        checker.arm_discovery(source,position)
        accept(checker)
        source,repairs = receipt(checker,24+number*10,position=position,after=True)
        checker.consume_discovery(source,position,repairs)
        if position!=UNTRACKED[-1]:
            assert checker.coverage.groups['checked'].coverage==pytest.approx(400/6)
    checker.finish()
    assert all(group.coverage==100 for group in checker.coverage.groups.values())


def test_mixed_beat_changes_exactly_the_four_logical_owners_without_allocating_unmatched_branches():
    checker,source = prepared()
    model = checker.model
    before = deepcopy(model.memory)
    checker.arm_learning(source)
    assert tuple(branch.position for branch in checker.pending[2].branches)==RESOLVED
    assert tuple(branch.matched for branch in checker.pending[2].branches)==(False,False,True,True,False,True,False,True)
    accept(checker)
    assert model.allocations==4 and before.keys()==model.memory.keys()
    assert len(before)==4
    for key,entry in before.items():
        assert entry.counter==2 and model.memory[key]==replace(entry,counter=1)
        table,bank,row,way = key
        assert model.useful[table,bank,row,way]==1
    view = lookup(model,pc=PC,positions=TRACKED)
    assert all(not view.read.matches(position) for position in UNTRACKED)


def test_semantic_base_program_has_one_reachable_taken_tail_and_two_bit_counter_postcondition():
    counters = dict.fromkeys(TRACKED,0)
    program = tuple(opposing_base_program())
    assert len(program)==8
    for outcomes in program:
        assert [p for p,taken,_ in outcomes if taken]==[outcomes[-1][0]]
        assert [p for p,_,wrong in outcomes if wrong]==[outcomes[-1][0]]
        assert tuple(p for p,_,_ in outcomes)==tuple(p for p in TRACKED if p<=outcomes[-1][0])
        for position,taken,_ in outcomes:
            counters[position]=max(0,min(3,counters[position]+(1 if taken else -1)))
    assert counters==dict.fromkeys(TRACKED,2)


@pytest.mark.parametrize('position',UNTRACKED)
def test_discovery_uses_a_complete_valid_not_taken_prefix_before_its_taken_tail(position):
    outcomes = discovery_outcomes(position)
    assert tuple(p for p,_,_ in outcomes)==tuple(p for p in RESOLVED if p<=position)
    assert sum(taken for _,taken,_ in outcomes)==sum(wrong for _,_,wrong in outcomes)==1
    assert outcomes[-1]==(position,True,True)
    assert all(not taken and not wrong for _,taken,wrong in outcomes[:-1])


@pytest.mark.parametrize('fault',('pc','history','truncated','slots','tracked-miss','untracked-hit','wrong-direction',
    'wrong-kind','wrong-mispredict','wrong-base','wrong-owner','wrong-counter','wrong-useful','wrong-alternative','too-early'))
def test_wrong_actual_mixed_feedback_cannot_receive_reached_or_checked_credit(fault):
    checker,source = prepared()
    checker.arm_learning(source)
    feedback,slots = checker.pending[2:]
    branches = list(feedback.branches)
    if fault=='pc':feedback=replace(feedback,pc=PC+8)
    elif fault=='history':feedback=replace(feedback,context=Context.from_recent(1))
    elif fault=='truncated':feedback=replace(feedback,branches=feedback.branches[:-1])
    elif fault=='slots':slots=tuple(reversed(slots))
    elif fault=='tracked-miss':branches[2]=replace(branches[2],matched=False)
    elif fault=='untracked-hit':branches[0]=replace(branches[0],matched=True)
    elif fault=='wrong-direction':branches[2]=replace(branches[2],taken=True)
    elif fault=='wrong-kind':branches[2]=replace(branches[2],kind=2)
    elif fault=='wrong-mispredict':branches[2]=replace(branches[2],mispredict=True)
    elif fault=='wrong-base':branches[2]=replace(branches[2],base_counter=1)
    elif fault!='too-early':
        field={'wrong-owner':'way','wrong-counter':'counter','wrong-useful':'useful','wrong-alternative':'alternative'}[fault]
        value=getattr(branches[2].hint,field)
        branches[2]=replace(branches[2],hint=replace(branches[2].hint,**{field:not value if type(value) is bool else value^1}))
    if tuple(branches)!=checker.pending[2].branches:feedback=replace(feedback,branches=tuple(branches))
    before = deepcopy(checker.model.memory)
    with pytest.raises((ScoreboardMismatch,ValueError)) as first:
        accept(checker,feedback=feedback,slots=slots,tick=source.meta_tick if fault=='too-early' else None)
    with pytest.raises(type(first.value)) as second:checker.finish()
    assert first.value is second.value and checker.model.memory==before
    assert all(group.coverage==0 for group in checker.coverage.groups.values())


@pytest.mark.parametrize('position',TRACKED)
@pytest.mark.parametrize('field',('providerWayIdx','providerTakenCtr_value','providerUsefulCtr_value'))
def test_corrupting_any_tracked_effect_is_rejected_without_completing_the_batch(position,field):
    checker,source = prepared()
    checker.arm_learning(source)
    accept(checker)
    after,repairs = receipt(checker,14,after=True)
    slot = next(slot for slot,p in enumerate((6,4,14,10)) if p==position)
    after.meta.resolve['tage_entries'][slot][field] ^= 1
    with pytest.raises(ScoreboardMismatch):checker.consume_learning(after,repairs)
    assert checker.coverage.groups['checked'].coverage==0 and not checker.learned


@pytest.mark.parametrize('fault',('missing','wrong-pc','wrong-target','wrong-tick','extra-final','counter','provider'))
def test_delayed_absence_requires_the_new_real_consumer_not_a_planned_probe(fault):
    checker,source = learned()
    position = UNTRACKED[0]
    checker.arm_discovery(source,position)
    accept(checker)
    after,repairs = receipt(checker,24,position=position,after=True)
    if fault=='missing':repairs=()
    elif fault=='extra-final':repairs=(*repairs,(after.meta_tick,replace(repairs[0][1],s2_override=0,s3_override=1)))
    elif fault=='counter':after.meta.resolve['mbtb_entries'][0][0]['counter_value']=1
    elif fault=='provider':after.meta.resolve['tage_entries'][0]['hasProvider']=1
    else:
        tick,prediction=repairs[0]
        if fault=='wrong-pc':prediction=replace(prediction,start_pc=PC+8)
        elif fault=='wrong-target':prediction=replace(prediction,target=target(position)+16)
        else:tick+=2
        repairs=((tick,prediction),)
    with pytest.raises(ScoreboardMismatch) as first:checker.consume_discovery(after,position,repairs)
    with pytest.raises(ScoreboardMismatch) as second:checker.finish()
    assert first.value is second.value and not checker.discovered
    assert checker.coverage.groups['checked'].coverage==pytest.approx(400/6)


def test_unaccepted_mixed_beat_old_source_or_missing_probe_cannot_pass():
    checker,source = prepared()
    checker.arm_learning(source)
    with pytest.raises(ScoreboardMismatch):checker.consume_learning(source,())
    checker,source = prepared()
    checker.arm_learning(source)
    accept(checker)
    with pytest.raises(ScoreboardMismatch):checker.consume_learning(source,())
    checker,_ = learned()
    with pytest.raises(ScoreboardMismatch):checker.finish()


def test_reset_expires_pending_receipts_and_all_partial_obligations():
    checker,source = learned()
    checker.arm_discovery(source,UNTRACKED[0])
    accept(checker)
    checker.capture_input(NS(tick=40),Events(reset=True))
    assert checker.pending is checker.accepted is None and not checker.learned and not checker.discovered
    assert not checker.expected and not checker.accepted_feedback and not checker.resolve_slots
    with pytest.raises(ScoreboardMismatch):checker.arm_learning(source)


def test_coverage_is_empty_until_acceptance_and_case_does_not_implement_checking_or_timing():
    checker,_ = prepared()
    assert all(group.coverage==0 for group in checker.coverage.groups.values())
    tree = ast.parse(Path('bpu/case/tage/interleaved.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','RisingEdge','FallingEdge','get_','set_','gather','create_task','Scoreboard'}
