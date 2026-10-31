"""Declared program semantics and synthetic corruption; never DUT credit."""
import ast
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.abtb.model.semantic import Entry, Read, Frame, Recency
from suites.frontend.bpu.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from suites.frontend.bpu.bpu.coverage.ahead_working_set import AheadWorkingSetCoverage
from suites.frontend.bpu.bpu.model.ahead_working_set import (SIZES, KINDS, LIFETIMES, AheadWorkingSetProgram,
    expected_branch, semantic_history, strong_counter)
from suites.frontend.bpu.bpu.model.abtb.alias import mainbtb_route
from suites.frontend.bpu.bpu.model.path_history import Checkpoint
from suites.frontend.bpu.bpu.model.selection import Branch, Choice, Kind, StackAction
from suites.frontend.bpu.mbtb.model.semantic import MbtbReference
from suites.frontend.bpu.bpu.model.ahead_working_set import PrefixWorkingSetProgram,PREFIX_PROFILES


@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('kinds', KINDS)
@pytest.mark.parametrize('lifetime', tuple(LIFETIMES))
def test_program_is_closed_capacity_safe_and_has_real_nonzero_history(size, kinds, lifetime):
    p = AheadWorkingSetProgram(size, kinds, lifetime)
    all_pcs = set()
    for cohort in range(p.cohorts):
        edges = p.edges(cohort)
        assert len(edges) == SIZES[size] and len({e.pc for e in edges}) == len(edges)
        assert edges[-1].target == edges[0].pc and edges[-1].kind == 3
        assert tuple(e.target for e in edges[:-1]) == tuple(e.pc for e in edges[1:])
        assert all(e.pc <= e.cfi_pc < e.pc+8 for e in edges)
        assert not all_pcs.intersection(e.pc for e in edges)
        all_pcs.update(e.pc for e in edges)
        routes = Counter()
        for e in edges:
            r = mainbtb_route(e.pc, e.position)
            routes[r['selected_physical_align'], r['internal_bank'], r['entry_set']] += 1
        assert max(routes.values()) <= 2
        assert all(h != 0 for h in semantic_history(p, cohort)[-1])
        assert any(e.kind == 1 for e in edges)
        assert (any(e.kind == 2 for e in edges)) == (kinds == 'mixed')
    assert len(p.rules) == (8 if lifetime == 'coexisting' else 10)


@pytest.mark.parametrize('profile',PREFIX_PROFILES)
def test_selective_working_set_prefix_roundtrip_is_owned_by_real_instruction_events(profile):
    from tests.bpu.scoreboard._ahead_prefix_program import PrefixProgram,ahead_view
    program=PrefixWorkingSetProgram(profile)
    p=PrefixProgram(program)
    p.prepare()
    before={i:ahead_view(p.bank,p.converge(i,(0,3))) for i in program.order}
    for counts in ((3,3),(0,0),(3,0)):
        for index in program.selected:
            p.establish(index,counts[0]>=2,counts[1]>=2)
            p.converge(index,counts)
        for index in program.order:
            source=p.converge(index,counts if index in program.selected else (0,3))
            view=ahead_view(p.bank,source)
            for position in (2,12):
                assert {k:v for k,v in view[position].items() if k!='counter'}=={
                    k:v for k,v in before[index][position].items() if k!='counter'}
            if index not in program.selected:assert view==before[index]
            if counts==(3,3):assert view[12]==before[index][12]


@pytest.mark.parametrize('profile',PREFIX_PROFILES)
def test_prefix_program_has_two_distinct_targets_and_real_predecessors_without_physical_sweep(profile):
    from suites.frontend.bpu.bpu.model.phr.model import path_hash
    p=PrefixWorkingSetProgram(profile)
    assert path_hash(p.initial_pc,p.initial_pc)==0
    assert len(p.selected)==3 and len(p.order)==6 and len(set(p.order))==6
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']
    for index in p.order:
        first,later=p.branches(index)
        assert first.pc==later.pc==p.pc(index) and first.position<8<=later.position
        assert first.target!=later.target and p.predecessor(index).target==first.pc


@pytest.mark.parametrize('choice_name,early,later,positions,wrong',(
    ('early',False,True,(2,),(True,)),
    ('later',False,True,(2,12),(False,False)),
    ('later',True,True,(2,),(True,)),
    ('none',False,False,(2,12),(False,False)),
    ('none',False,True,(2,12),(False,True))))
def test_prefix_truth_stops_at_first_error_or_taken_and_never_invents_unexecuted_suffix(choice_name,early,later,positions,wrong):
    from suites.frontend.bpu.bpu.model.selection import fallthrough
    p=PrefixWorkingSetProgram(PREFIX_PROFILES[0]);edges=p.branches(0)
    choice=(fallthrough(p.pc(0)).branch if choice_name=='none' else
        Branch(edges[choice_name=='later'].position,edges[choice_name=='later'].target,Kind.CONDITIONAL,True))
    result=p.outcomes(0,choice,early_taken=early,later_taken=later)
    assert tuple(b.position for b in result)==positions
    assert tuple(b.mispredict for b in result)==wrong


@pytest.fixture(scope='module')
def complete_prefix_source():
    from tests.bpu.scoreboard._ahead_prefix_program import PrefixProgram
    p=PrefixProgram(PrefixWorkingSetProgram(PREFIX_PROFILES[0]));p.prepare()
    return p,p.converge(0,(0,3))


@pytest.mark.parametrize('fault',('earlier-counter','later-counter','target','kind','position','duplicate-hit','early-choice'))
def test_prefix_consumer_rejects_complete_identity_or_strength_corruption(complete_prefix_source,monkeypatch,fault):
    from suites.frontend.bpu.bpu.checker.ahead_working_set import prefix_consumer_matches
    p,token=complete_prefix_source
    original=p.bank.snapshot(token)
    frame=original.frame
    ways={entry.position:i for i,(entry,hit) in enumerate(zip(frame.read.entries,frame.hits,strict=True)) if hit}
    entries=list(frame.read.entries);counters=list(frame.counters)
    if fault.endswith('counter'):counters[ways[2 if fault.startswith('earlier') else 12]]^=1
    elif fault in ('target','kind','position'):
        entry=entries[ways[12]]
        entries[ways[12]]=replace(entry,**{fault:getattr(entry,fault)^1})
    elif fault=='duplicate-hit':entries[next(i for i,hit in enumerate(frame.hits) if not hit)]=entries[ways[12]]
    else:token=replace(token,early=replace(token.early,branch=replace(token.early.branch,target=token.early.branch.target+2)))
    modified=replace(frame,read=replace(frame.read,entries=tuple(entries)),counters=tuple(counters))
    monkeypatch.setattr(p.bank,'snapshot',lambda _:replace(original,frame=modified))
    assert not prefix_consumer_matches(p.bank,token,p.program,0,(0,3))


@pytest.mark.parametrize('phase',('initial-late','selected-early','selected-NT','restored-early'))
def test_prefix_lifetime_cannot_close_without_every_real_consumer_phase(phase):
    from suites.frontend.bpu.bpu.checker.ahead_working_set import PrefixWorkingSetChecks
    from suites.frontend.bpu.bpu.coverage.ahead_working_set import PrefixWorkingSetCoverage
    p=PrefixWorkingSetProgram(PREFIX_PROFILES[0]);coverage=PrefixWorkingSetCoverage(p)
    checks=PrefixWorkingSetChecks(p,coverage)
    checks.pipeline=NS(current_event=None,raise_failure=lambda:None)
    checks.original_residents={i:{} for i in range(p.count)}
    checks.prefix_consumers=[dict(phase=name,index=i,owner=100*k+i) for k,name in enumerate(
        ('initial-late','selected-early','selected-NT','restored-early')) for i in range(p.count)
        if name!=phase or i!=p.selected[0]]
    with pytest.raises(AssertionError):checks.finish_prefix()
    assert not checks.prefix_closed and coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('kind,counter', ((1, 3), (2, 2), (3, 2)))
def test_only_conditional_records_are_rewarded_after_their_own_initialization(kind, counter):
    edge = replace(AheadWorkingSetProgram('turnover', 'mixed', 'coexisting').edges(0)[0], kind=kind)
    assert strong_counter(edge) == counter
    assert expected_branch(edge) == dict(taken=True, position=7, target=edge.target, kind=kind, action=0)


def state_fixture():
    p = AheadWorkingSetProgram('turnover', 'mixed', 'coexisting')
    checks = AheadWorkingSetChecks(p, AheadWorkingSetCoverage(p))
    edge = p.edges(0)[1]  # A genuine conditional body edge.
    entry = Entry(True, edge.pc % (1 << 24), edge.position, edge.kind, 0, edge.target % (1 << 22))
    key = (0, 0, 0)
    ahead = NS(counters={key:3}, recency={}, memory={key:entry})
    frame = Frame(Read(0, 0, (entry, Entry(), Entry(), Entry())), edge.pc, (3,0,0,0))
    token = NS(pc=edge.pc, sequence=1, history=Checkpoint(1, 123, 1),
        early=Choice(Branch(edge.position, edge.target, Kind(edge.kind), True, StackAction.NONE), 0, 'ahead'))
    sources = NS(ahead=ahead, main=MbtbReference(), snapshot=lambda _:NS(frame=frame))
    pipeline = NS(current_event=NS(tick=100), model=NS(sources=sources), raise_failure=lambda:None)
    checks.pipeline = pipeline
    main_bank = dict(writes=tuple(dict(valid=0,ready=0,bits={}) for _ in range(3)), direction=dict(valid=0))
    state = dict(counters=(3,)+(0,)*1023, recency=(0,)*256,
        main_service=tuple(deepcopy(main_bank) for _ in range(4)),main_response={},tage_fast=())
    row = dict(observed=dict(ahead_working_state=state))
    cycle = NS(metadata=token, decisions=(None,None,token.early))
    checks.begin(0,'warm')
    return checks, row, NS(metadata_ready=True), cycle, pipeline.model, token, frame


def observe(checks, row, events, cycle, model):
    checks.candidates(row,events,cycle,model,None,None)
    checks.checked(checks.pipeline.current_event.tick)


def test_complete_state_and_owned_source_qualify_the_consumer_not_only_a_taken_bit():
    checks,row,events,cycle,model,token,frame = state_fixture()
    observe(checks,row,events,cycle,model)
    assert set(checks.seen) == {token.pc}
    assert checks.seen[token.pc]['counter'] == 3
    assert checks.counter_comparisons == 1024 and checks.recency_comparisons == 256
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('target-counter','untouched-counter','recency','wrong-target',
                                  'wrong-kind','wrong-position','duplicate-hit'))
def test_bad_state_or_identity_cannot_qualify_a_consumer(fault):
    checks,row,events,cycle,model,token,frame = state_fixture()
    state = row['observed']['ahead_working_state']
    if fault in ('target-counter','untouched-counter'):
        cells = list(state['counters']); cells[0 if fault == 'target-counter' else 999] ^= 1
        state['counters'] = tuple(cells)
    elif fault == 'recency': state['recency'] = (1,)+(0,)*255
    elif fault in ('wrong-target','wrong-kind','wrong-position'):
        branch = token.early.branch
        changed = replace(branch, **{'wrong-target':dict(target=branch.target+8),
            'wrong-kind':dict(kind=Kind.DIRECT), 'wrong-position':dict(position=branch.position-1)}[fault])
        cycle.decisions = (None,None,replace(token.early,branch=changed))
    else:
        entry = frame.read.entries[0]
        new = replace(frame,read=replace(frame.read,entries=(entry,entry,Entry(),Entry())))
        model.sources.snapshot = lambda _:NS(frame=new)
    with pytest.raises(AssertionError): observe(checks,row,events,cycle,model)
    assert not checks.seen and checks.coverage.groups['checked'].coverage == 0


def test_a_new_service_is_not_confirmed_until_next_actual_full_state_boundary():
    checks,row,events,cycle,model,token,frame = state_fixture()
    checks.candidates(row,events,cycle,model,None,None)
    old = model.sources.ahead.memory[0,0,0]
    model.sources.ahead.memory[0,0,0] = replace(old,tag=old.tag+1)
    model.sources.ahead.counters[0,0,0] = 2
    checks.checked(100)
    assert checks.services == checks.strong_resets == 0
    assert checks.pending_services[0]['old_counter'] == 3
    row['observed']['ahead_working_state']['counters'] = (2,)+(0,)*1023
    cycle.metadata = None
    checks.candidates(row,events,cycle,model,None,None)
    assert checks.services == checks.strong_resets == 1
    assert not checks.pending_services


def test_wrong_new_identity_confidence_is_not_normalized_to_a_dut_seed():
    checks,row,events,cycle,model,token,frame = state_fixture()
    checks.candidates(row,events,cycle,model,None,None)
    old = model.sources.ahead.memory[0,0,0]
    model.sources.ahead.memory[0,0,0] = replace(old,tag=old.tag+1)
    with pytest.raises(AssertionError): checks.checked(100)
    assert checks.services == 0 and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-lap','missing-feedback','mutated-original','pending-service'))
def test_lifetime_cannot_close_with_incomplete_work_or_mutated_originals(fault):
    p = AheadWorkingSetProgram('turnover','conditional','coexisting')
    checks = AheadWorkingSetChecks(p,AheadWorkingSetCoverage(p))
    checks.pipeline = NS(raise_failure=lambda:None,current_event=NS(tick=1))
    source = NS(meta=NS(resolve=dict(pc=1),redirect=dict(history=0)))
    checks.originals = [(source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect))]
    checks.lifetimes = [dict(consumers=16)]*2
    checks.feedback_receipts = [dict(bridge=False)]*16
    if fault == 'missing-lap': checks.lifetimes.pop()
    elif fault == 'missing-feedback': checks.feedback_receipts.pop()
    elif fault == 'mutated-original': source.meta.resolve['pc'] = 2
    else: checks.pending_services.append(dict())
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_case_expresses_lifetimes_not_signal_edges_and_inputs_do_not_depend_on_native_gaps():
    path = Path('bpu/case/ahead_working_set.py')
    tree = ast.parse(path.read_text())
    forbidden = {'RisingEdge','FallingEdge','ClockCycles','gather','create_task','get_','set_'}
    assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
    assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
    text = Path('bpu/model/ahead_working_set.py').read_text()
    assert all(word not in text for word in ('memory_signal','lcov','coverage.info','native_rows','toffee'))
