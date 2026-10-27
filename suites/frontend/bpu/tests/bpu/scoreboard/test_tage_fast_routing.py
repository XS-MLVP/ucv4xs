"""Pure independent learning and negative end-to-end routing qualification."""
from copy import deepcopy
from dataclasses import replace
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from bpuverify.bpu.agent.main import BpuAgent
from bpuverify.bpu.case.definitions import PC, POSITION, LATER_POSITION, EARLIER_TARGET, LATER_TARGET
from bpuverify.bpu.checker.tage.fast_routing import TageRoutingChecker, observed_phase
from bpuverify.bpu.coverage.tage.fast_routing import RoutingCoverage,DISCOVERIES
from bpuverify.bpu.model.selection import fallthrough
from bpuverify.bpu.transaction.types import BpuPrediction
from bpuverify.tage.model.semantic import Base, Branch, Context, Events, Feedback, Hint, decide
from tests.tage.scoreboard.test_semantic_model import actual_prediction, learn, lookup
from tests.bpu.scoreboard.test_phr_api import fake_agent


def checked_source(*,strong=False,swapped=False,checker=None,discovery='earlier-first'):
    checker = TageRoutingChecker(RoutingCoverage(discovery),pc=PC,positions=(POSITION,LATER_POSITION),
        targets=(EARLIER_TARGET,LATER_TARGET)) if checker is None else checker
    model = checker.model
    if not checker.discoveries:
        order = checker.positions if checker.coverage.discovery=='earlier-first' else checker.positions[::-1]
        checker.capture_input(SimpleNamespace(tick=-4),Events(reset=True,enabled=False))
        for tick,position in enumerate(order):
            checker.capture_input(SimpleNamespace(tick=-3+tick*2),Events(enabled=False,
                feedback=Feedback(PC,Context(),(Branch(position,True,1,True,False),))))
        checker.raise_failure()
    model.reset()
    def allocate(position,taken,owner):
        tx = Feedback(PC,Context(),(Branch(position,taken,1,True,True,0 if taken else 2),))
        for _ in range(128):
            if model.allocation_at_next_accept(tx)==owner:
                break
            model.advance()
        else:
            raise AssertionError('pure independent allocation opportunity not reached')
        learn(model,tx)
    allocate(POSITION,False,(2,0))
    learn(model,Feedback(PC,Context(),(Branch(POSITION,False,1,False,True,1,
        Hint(True,False,False,2,0,3,0,False,False)),)))
    allocate(LATER_POSITION,True,(2,1))
    if strong:
        learn(model,Feedback(PC,Context(),(Branch(LATER_POSITION,True,1,False,True,1,
            Hint(True,False,False,2,1,4,0,False,False)),)))
    positions = (LATER_POSITION,POSITION,0,0) if swapped else (POSITION,LATER_POSITION,0,0)
    frame = lookup(model,pc=PC,positions=positions)
    base = {POSITION:Base(True,POSITION,False,True,1),LATER_POSITION:Base(True,LATER_POSITION,strong,False,1)}
    bases = tuple(base.get(p,Base()) for p in positions)
    checker.initialized = True
    tick = checker.expected[-1][0]+16 if checker.expected else 4
    checker.events,checker.input_tick = Events(advance=True),tick-1
    wanted = decide(frame,bases,model.selectors)
    actual = actual_prediction(wanted)
    extras = {name:tuple(wanted.get(f'{slot}.{field}',0) for slot in range(4))
              for name,field in (('fast_valids','fast_valid'),('fast_takens','fast_taken'),('sc_counters','sc_counter'))}
    checker.capture_output(SimpleNamespace(tick=tick),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    branch = fallthrough(PC).branch
    source = SimpleNamespace(prediction_tick=tick,meta_tick=tick+4,
        prediction=BpuPrediction(PC,branch.target,0,branch.position,0,0),
        meta=SimpleNamespace(resolve={'tage_entries':deepcopy(actual.metas)}))
    repairs = [(tick+2,BpuPrediction(PC,LATER_TARGET,1,LATER_POSITION,1,0))]
    if not strong:
        repairs.append((tick+4,BpuPrediction(PC,branch.target,0,branch.position,0,1)))
    return checker,source,tuple(repairs),(frame,bases,actual,extras)


@pytest.mark.parametrize('swapped',(False,True))
@pytest.mark.parametrize('discovery',DISCOVERIES)
def test_two_distinct_owned_directions_and_complete_consumers_qualify_all_event_rules(swapped,discovery):
    checker,source,repairs,_ = checked_source(swapped=swapped,discovery=discovery)
    assert checker.consumer(source,repairs)=='weak'
    checker,source,repairs,_ = checked_source(strong=True,swapped=swapped,checker=checker)
    assert checker.consumer(source,repairs)=='strong'
    checker.finish()
    assert all(group.coverage==100 for group in checker.coverage.groups.values())


@pytest.mark.parametrize('fault',('missing-middle','missing-late','extra','same-target-extra','wrong-target','wrong-pc','wrong-tick','wrong-stage','metadata'))
def test_wrong_or_extra_repair_is_not_hidden_by_expected_target_search(fault):
    checker,source,repairs,_ = checked_source()
    repairs = list(repairs)
    if fault=='missing-middle': repairs.pop(0)
    elif fault=='missing-late': repairs.pop()
    elif fault in ('extra','same-target-extra'): repairs.insert(1,(7,repairs[0][1]))
    elif fault=='wrong-target': repairs[0] = 6,replace(repairs[0][1],target=LATER_TARGET+16)
    elif fault=='wrong-pc': repairs[0] = 6,replace(repairs[0][1],start_pc=PC+16)
    elif fault=='wrong-tick': repairs[0] = 10,repairs[0][1]
    elif fault=='wrong-stage': repairs[0] = 6,replace(repairs[0][1],s2_override=0,s3_override=1)
    else: source.meta.resolve['tage_entries'][1]['providerTakenCtr_value'] ^= 1
    before = deepcopy(checker.model.state())
    with pytest.raises(ScoreboardMismatch) as first:
        checker.consumer(source,tuple(repairs))
    assert checker.model.state()==before and checker.coverage.groups['checked'].coverage==20
    with pytest.raises(ScoreboardMismatch) as second: checker.consumer(source,())
    assert first.value is second.value


def test_strong_provider_cannot_silently_emit_an_extra_same_target_s3_override():
    checker,source,repairs,_ = checked_source()
    checker.consumer(source,repairs)
    checker,source,repairs,_ = checked_source(strong=True,checker=checker)
    extra = (source.meta_tick,replace(repairs[0][1],s2_override=0,s3_override=1))
    with pytest.raises(ScoreboardMismatch): checker.consumer(source,(*repairs,extra))
    assert checker.coverage.groups['checked'].coverage==60


def test_corrupt_raw_direction_records_reached_but_never_checked_oracle_credit():
    checker,_,_,(_,bases,actual,extras) = checked_source()
    checker.coverage = RoutingCoverage()
    checker.input_tick = 5
    extras['fast_takens'] = (0,0,0,0)
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=6),actual,bases=bases,enabled=True,extras=extras)
    with pytest.raises(ScoreboardMismatch,match='fast_taken'): checker.finish()
    assert checker.model.state()==before
    assert checker.coverage.groups['reached'].coverage==20
    assert checker.coverage.groups['checked'].coverage==0


def test_held_old_frame_does_not_count_as_a_fresh_opposed_owner_prediction_event():
    checker,_,_,(_,bases,actual,extras) = checked_source()
    checker.coverage = RoutingCoverage()
    checker.events = replace(checker.events,advance=False)
    checker.input_tick = 5
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=6),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    assert checker.model.state()==before
    assert all(group.coverage==0 for group in checker.coverage.groups.values())
    assert all(tick!=6 for tick,phase in checker.routes)


@pytest.mark.parametrize('fault',('same-owner','no-provider','same-direction','missing-base','wrong-position','alternate'))
def test_unqualified_component_state_or_planned_phase_cannot_earn_routing_credit(fault):
    _,_,_,(frame,bases,actual,_) = checked_source()
    actual = deepcopy(actual)
    if fault=='same-owner': actual.metas[1]['providerWayIdx'] = 0
    elif fault=='no-provider': actual.metas[1]['hasProvider'] = 0
    elif fault=='same-direction': actual.metas[0]['providerTakenCtr_value'] = 5
    elif fault=='missing-base': bases = (bases[0],Base(),*bases[2:])
    elif fault=='wrong-position': frame = replace(frame,positions=(POSITION,7,0,0))
    else: actual.metas[1]['hasAlt'] = 1
    assert observed_phase(frame,bases,actual,(POSITION,LATER_POSITION)) is None


async def test_production_window_collector_keeps_wrong_pc_duplicates_and_unexpected_targets():
    agent = fake_agent()
    source = SimpleNamespace(prediction_tick=4,meta_tick=8)
    good = BpuPrediction(PC,LATER_TARGET,1,LATER_POSITION,1,0)
    wrong = replace(good,start_pc=PC+16,target=LATER_TARGET+16)
    rows = iter((SimpleNamespace(accepted_tick=tick,value=p) for tick,p in (
        (4,good),(6,wrong),(6,wrong),(8,replace(good,s2_override=0,s3_override=1)),(10,good))))
    async def recv(): return next(rows)
    agent.prediction_monitor = SimpleNamespace(recv=recv)
    assert await agent.corrections_for(source)==((6,wrong),(6,wrong),(8,replace(good,s2_override=0,s3_override=1)))


async def test_collection_budget_cannot_turn_an_unclosed_window_into_a_success():
    agent = fake_agent()
    source = SimpleNamespace(prediction_tick=4,meta_tick=8)
    async def recv(): return SimpleNamespace(accepted_tick=6,value=BpuPrediction(PC,LATER_TARGET,1,LATER_POSITION,1,0))
    agent.prediction_monitor = SimpleNamespace(recv=recv)
    with pytest.raises(AssertionError,match='did not close'): await agent.corrections_for(source,limit=2)


def discovery_checker(discovery='later-first'):
    checker = TageRoutingChecker(RoutingCoverage(discovery),pc=PC,positions=(POSITION,LATER_POSITION),
        targets=(EARLIER_TARGET,LATER_TARGET))
    checker.capture_input(SimpleNamespace(tick=0),Events(reset=True,enabled=False))
    return checker


def discover(checker,position,tick=2,**changes):
    events = Events(enabled=False,feedback=Feedback(PC,Context(),(Branch(position,True,1,True,False),)))
    checker.capture_input(SimpleNamespace(tick=tick),replace(events,**changes))


@pytest.mark.parametrize('discovery',DISCOVERIES)
def test_wrong_accepted_discovery_order_cannot_be_relabelled_as_the_requested_scenario(discovery):
    checker = discovery_checker(discovery)
    wrong = LATER_POSITION if discovery=='earlier-first' else POSITION
    before = deepcopy(checker.model.memory)
    discover(checker,wrong)
    with pytest.raises(ScoreboardMismatch) as first:checker.raise_failure()
    with pytest.raises(ScoreboardMismatch) as second:checker.finish()
    assert first.value is second.value and not checker.discoveries
    assert checker.model.memory==before
    assert all(group.coverage==0 for group in checker.coverage.groups.values())


@pytest.mark.parametrize('fault',('duplicate','simultaneous','backward'))
def test_two_discovery_labels_need_distinct_ordered_actual_acceptances(fault):
    checker = discovery_checker()
    discover(checker,LATER_POSITION)
    discover(checker,LATER_POSITION if fault=='duplicate' else POSITION,
        tick=4 if fault=='duplicate' else 2 if fault=='simultaneous' else 1)
    with pytest.raises(ScoreboardMismatch):checker.raise_failure()
    assert len(checker.discoveries)==1
    assert all(group.coverage==0 for group in checker.coverage.groups.values())


@pytest.mark.parametrize('fault',('unready','other-pc','not-taken','not-conditional','not-wrong','already-known','other-position'))
def test_unqualified_feedback_does_not_establish_a_branch_discovery(fault):
    checker = discovery_checker()
    branch = Branch(LATER_POSITION,True,1,True,False)
    if fault=='not-taken':branch=replace(branch,taken=False)
    elif fault=='not-conditional':branch=replace(branch,kind=2)
    elif fault=='not-wrong':branch=replace(branch,mispredict=False)
    elif fault=='already-known':branch=replace(branch,matched=True)
    elif fault=='other-position':branch=replace(branch,position=15)
    checker.capture_input(SimpleNamespace(tick=2),Events(enabled=False,ready=fault!='unready',
        feedback=Feedback(PC+16 if fault=='other-pc' else PC,Context(),(branch,))))
    checker.raise_failure()
    assert not checker.discoveries
    with pytest.raises(ScoreboardMismatch):checker.finish()


def test_opposed_directions_without_actual_discoveries_do_not_earn_event_credit():
    checker,_,_,(_,bases,actual,extras) = checked_source(discovery='later-first')
    checker.coverage = RoutingCoverage('later-first')
    checker.discoveries.clear()
    checker.input_tick = 5
    checker.capture_output(SimpleNamespace(tick=6),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    assert all(group.coverage==0 for group in checker.coverage.groups.values())


def test_reset_expires_discovery_and_consumer_evidence_instead_of_reusing_old_order():
    checker,source,repairs,_ = checked_source(discovery='later-first')
    checker.consumer(source,repairs)
    assert checker.discoveries and checker.routes and checker.neighbor is not None
    checker.capture_input(SimpleNamespace(tick=20),Events(reset=True,enabled=False))
    assert not checker.discoveries and not checker.routes and checker.neighbor is None
    with pytest.raises(ScoreboardMismatch):checker.finish()


def test_planned_phase_label_cannot_close_a_different_actual_consumer():
    checker,source,repairs,_ = checked_source(discovery='later-first')
    with pytest.raises(ScoreboardMismatch):checker.consumer(source,repairs,phase='strong')
    assert checker.coverage.groups['checked'].coverage==20


def test_a_source_predating_the_discoveries_cannot_qualify_the_new_program_history():
    checker,source,repairs,_ = checked_source(discovery='later-first')
    checker.discoveries = [(source.prediction_tick-2,LATER_POSITION),(source.prediction_tick,POSITION)]
    with pytest.raises(ScoreboardMismatch):checker.consumer(source,repairs)
    assert checker.coverage.groups['checked'].coverage==20


@pytest.mark.parametrize('fault',('missing-provider','wrong-table','wrong-owner','wrong-counter'))
def test_earlier_preparation_is_checked_by_the_reference_with_context(fault):
    checker,source,_,_ = checked_source(discovery='later-first')
    meta = dict(checker.source_expected(source,POSITION))
    if fault=='missing-provider':meta={'hasProvider':0}
    else:meta[{'wrong-table':'providerTableIdx','wrong-owner':'providerWayIdx','wrong-counter':'providerTakenCtr_value'}[fault]] ^= 1
    checker.source_expected = lambda *args:meta
    with pytest.raises(ScoreboardMismatch) as first:checker.earlier_ready(source)
    with pytest.raises(ScoreboardMismatch) as second:checker.raise_failure()
    assert first.value is second.value


def test_case_leaves_comparison_and_cycle_timing_in_the_checker_and_environment():
    tree = ast.parse(Path('bpuverify/bpu/case/tage/fast_routing.py').read_text())
    for node in ast.walk(tree):
        assert not isinstance(node,(ast.Assert,ast.ClassDef))
        if isinstance(node,ast.Call):
            name = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
            assert name not in {'ClockCycles','RisingEdge','FallingEdge','get_','set_','gather','create_task','Scoreboard'}
