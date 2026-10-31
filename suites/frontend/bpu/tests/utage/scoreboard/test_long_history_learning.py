"""Independent arithmetic and deliberately wrong synthetic observations only."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from toffee import TransferState
from suites.frontend.bpu.utage.checker.long_history_learning import LongHistoryLearningChecks
from suites.frontend.bpu.utage.coverage.long_history_learning import LongHistoryLearningCoverage
from suites.frontend.bpu.utage.model.long_history_learning import (LongHistoryLearning, PC, POSITION, HISTORIES,
    MODES, PHASES, address, expected)
from suites.frontend.bpu.utage.model.usefulness_events import ProtectionState
from suites.frontend.bpu.utage.transaction.types import UtageLookup, UtagePrediction


def prediction(path, counter, *, base=None, table=1):
    base = int(path=='a') if base is None else base
    fields = expected(path,base,table=table,counter=counter)
    slots = tuple(dict(valid=int(i==0),cfiPosition=5+i,baseTaken=base if i==0 else 0,
        baseIsStrongBias=0,hit=int(i==0 and counter is not None),tableId=table,
        takenCtr_value=counter or 0,predTaken=int((counter or 0)>=4)) for i in range(4))
    return UtagePrediction(fields['hit'],int((counter or 0)>=4),dict(readIndex=address(path),
        foldedPathHistForTrain_hist=tuple(dict(foldedHist=f) for f in fields['folds']),abtbResult=slots))


def transfer(path, tick):
    return NS(state=TransferState.COMPLETED,accepted_event=NS(tick=tick),completed_event=NS(tick=tick+4),
              request=UtageLookup(PC,POSITION,int(path=='a'),folded_history=HISTORIES[path]))


def capture(checks, paths, tick):
    transfers = tuple(transfer(p,tick+2*i) for i,p in enumerate(paths))
    results = tuple(prediction(p,checks.ledger.states[p].counter) for p in paths)
    return checks.capture(paths,transfers,results)


def inputs(checks, rule, batch, start=100):
    _,states = checks.ledger.preview(batch)
    values = [0]*1024
    for path,state in states.items():values[512+address(path)[1]] = state.useful
    payloads = tuple(dict(owner=owner) for owner,_ in batch)
    step = 2 if checks.mode=='adjacent' else 4
    receipts = tuple((start+step*i,p) for i,p in enumerate(payloads))
    tick = start+step*len(batch)+10
    consumers = {p:(transfer(p,tick+2+2*i),prediction(p,s.counter)) for i,(p,s) in enumerate(states.items())}
    return [rule,batch,receipts,payloads,values,consumers],dict(tick=tick,cycle_ticks=2)


def advance(checks, rule, batch, start=100):
    args,kwargs = inputs(checks,rule,batch,start)
    checks.verified_phase(*args,**kwargs)


def program(mode):
    checks = LongHistoryLearningChecks(mode,LongHistoryLearningCoverage(mode))
    checks.reach('prepared-distinct-long-paths')
    owners = capture(checks,('a','b')*3,2)
    advance(checks,'independent-cumulative-learning',tuple(zip(owners,(0,1)*3)))
    owners = capture(checks,('a','b')*2,1000)
    advance(checks,'opposed-boundary-holds',((owners[1],1),(owners[0],0)),1100)
    advance(checks,'reverse-from-boundaries',((owners[2],1),(owners[3],0)),1200)
    checks.reach('shared-short-fallback'); checks.reach('cold-neighbor-isolation')
    return checks


@pytest.mark.parametrize('mode',MODES)
def test_opposed_paths_accumulate_from_distinct_sources_and_recover_without_shared_state_damage(mode):
    checks = program(mode)
    assert checks.ledger.states==dict(a=ProtectionState(1,2),b=ProtectionState(6,2))
    assert len(checks.ledger.consumed)==10 and checks.coverage.groups['checked'].coverage==0
    checks.finish()
    assert checks.coverage.groups['checked'].coverage==50


def test_program_geometry_shares_short_but_distinguishes_long_and_cold_without_a_bank_sweep():
    model = LongHistoryLearning()
    assert {address(p)[0] for p in ('a','b','fallback')}=={0}
    assert tuple(address(p)[1] for p in ('a','b','fallback'))==(32,160,96)
    assert address('cold')[0]!=0
    assert model.states==dict(a=ProtectionState(3,2),b=ProtectionState(4,2))


@pytest.mark.parametrize('fault',('duplicate','missing','consumed','invalid-direction'))
def test_invalid_source_batch_cannot_partially_advance_the_logical_model(fault):
    model = LongHistoryLearning();model.capture(1,'a',1);model.capture(2,'b',0)
    if fault=='consumed':model.commit(((1,0),))
    before = deepcopy(model.state())
    batch = {'duplicate':((1,0),(1,0)), 'missing':((1,0),(999,1)),
             'consumed':((1,0),(2,1)), 'invalid-direction':((1,0),(2,2))}[fault]
    with pytest.raises(ValueError):model.commit(batch)
    assert model.state()==before


@pytest.mark.parametrize('fault',('protection','other-path','shared-short','cold-neighbor','payload',
                                 'missing-feedback','bubble','serialised','missing-consumer',
                                 'wrong-counter','old-consumer','same-totals-wrong-interleaving'))
def test_actual_phase_damage_does_not_advance_ledger_or_receive_checked_credit(fault):
    checks = LongHistoryLearningChecks('adjacent',LongHistoryLearningCoverage('adjacent'))
    owners = capture(checks,('a','b')*3,2);batch = tuple(zip(owners,(0,1)*3))
    args,kwargs = inputs(checks,'independent-cumulative-learning',batch)
    if fault in ('protection','other-path','shared-short','cold-neighbor'):
        address_ = {'protection':512+address('a')[1], 'other-path':512+address('b')[1],
                    'shared-short':address('a')[0], 'cold-neighbor':address('cold')[0]}[fault]
        args[4][address_] ^= 1
    elif fault=='payload':args[2] = ((100,dict(owner=999)),*args[2][1:])
    elif fault=='missing-feedback':args[2] = args[2][:-1]
    elif fault in ('bubble','serialised'):
        args[2] = tuple((tick+(2*int(i>=3) if fault=='bubble' else 2*i),p)
                        for i,(tick,p) in enumerate(args[2]))
    elif fault=='missing-consumer':del args[5]['a']
    elif fault=='wrong-counter':args[5]['a'] = args[5]['a'][0],prediction('a',3)
    elif fault=='old-consumer':args[5]['a'][0].accepted_event.tick = kwargs['tick']
    else:
        order = (0,2,4,1,3,5);args[1] = tuple(batch[i] for i in order)
        args[3] = tuple(args[3][i] for i in order)
        args[2] = tuple((100+2*i,p) for i,p in enumerate(args[3]))
    before = deepcopy(checks.ledger.state())
    with pytest.raises(AssertionError):checks.verified_phase(*args,**kwargs)
    assert checks.ledger.state()==before and checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('wrong-request','wrong-output','no-overlap','unfinished','missing-output'))
def test_source_capture_requires_actual_complete_and_distinct_owned_queries(fault):
    checks = LongHistoryLearningChecks('adjacent',LongHistoryLearningCoverage('adjacent'))
    paths = ('a','b');ts = tuple(transfer(p,2+2*i) for i,p in enumerate(paths))
    predictions = tuple(prediction(p,checks.ledger.states[p].counter) for p in paths)
    if fault=='wrong-request':ts[1].request = replace(ts[1].request,folded_history=HISTORIES['a'])
    elif fault=='wrong-output':predictions = predictions[::-1]
    elif fault=='no-overlap':ts[1].accepted_event.tick = ts[0].completed_event.tick
    elif fault=='unfinished':ts[1].state = TransferState.PROCESSING
    else:predictions = predictions[:-1]
    with pytest.raises(AssertionError):checks.capture(paths,ts,predictions)
    assert checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-consumer','missing-boundary','duplicate-source','mutated-snapshot'))
def test_all_semantic_obligations_and_original_snapshots_are_required_before_closure(fault):
    checks = program('adjacent')
    if fault=='missing-consumer':checks.completed.remove('shared-short-fallback')
    elif fault=='missing-boundary':checks.completed.remove('opposed-boundary-holds')
    elif fault=='duplicate-source':checks.ledger.consumed.pop()
    else:checks.originals[0][0].meta['abtbResult'][0]['takenCtr_value'] ^= 1
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage==0


def test_case_and_reference_have_no_clock_edges_raw_io_or_async_join_details():
    case = ast.parse(Path('utage/case/long_history_learning.py').read_text())
    forbidden = {'ClockCycles','RisingEdge','FallingEdge','gather','create_task','set_','get_'}
    assert not {n.id for n in ast.walk(case) if isinstance(n,ast.Name)}&forbidden
    assert not {n.attr for n in ast.walk(case) if isinstance(n,ast.Attribute)}&forbidden
    model = ast.parse(Path('utage/model/long_history_learning.py').read_text())
    assert not any(isinstance(n,ast.ImportFrom) and n.module and any(
        p in n.module.split('.') for p in ('driver','monitor','bundle','toffee')) for n in ast.walk(model))


def test_generator_feedback_is_consumed_once_and_state_reports_cannot_rewrite_history_identity():
    ledger = LongHistoryLearning();ledger.capture(1,'a',1);ledger.capture(2,'b',0)
    ledger.commit((item for item in ((1,0),(2,1))))
    assert ledger.consumed=={1,2}
    state = ledger.state();state['histories']['a'] = 0
    assert ledger.state()['histories']['a']==HISTORIES['a']
    with pytest.raises(ValueError):ledger.commit(((1,0),))
