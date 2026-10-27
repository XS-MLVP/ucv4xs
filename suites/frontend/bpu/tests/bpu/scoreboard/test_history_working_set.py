"""Path ancestry, declared capacity and corruption checks, with no DUT credit."""
import ast
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.history_working_set import HistoryWorkingSetChecks
from bpuverify.bpu.coverage.history_working_set import HistoryWorkingSetCoverage
from bpuverify.bpu.env.history_working_set import HistoryWorkingSetEnv
from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.model.history_working_set import (ANCHOR,FEATURES,POSITION,PROFILES,
    HistoryLearningLedger,HistoryWorkingSetProgram,history_path,main_capacity)
from bpuverify.bpu.model.pipeline import PipelineReference,Events
from bpuverify.mbtb.model.semantic import Entry as MainEntry,Target,coordinate,tag
from bpuverify.utage.model.semantic import Entry,UtageReference
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.bpu.model.history_working_set import ShortWorkingSetProgram,SHORT_PROFILES,SHORT_RULES,short_history_path
from bpuverify.bpu.coverage.history_working_set import ShortPathRetentionCoverage
from bpuverify.bpu.checker.history_working_set import ShortPathRetentionChecks
from bpuverify.bpu.model.early_protection import ProtectionLedger
from bpuverify.bpu.model.history_working_set import (ShortMixedWorkingSetProgram,SHORT_MIXED_PROFILES,
    SHORT_MIXED_RULES,SHORT_TURNAROUND_PATHS,SHORT_RESTORATION_PATHS,short_learning_path)
from bpuverify.bpu.checker.history_working_set import ShortMixedPathChecks
from bpuverify.bpu.coverage.history_working_set import ShortMixedPathCoverage


@pytest.mark.parametrize('taken,protection',((False,1),(False,2),(True,0),(True,2)))
async def test_stable_mixed_direction_does_not_require_unearned_protection(taken,protection):
    from bpuverify.bpu.case.history_working_set import _mixed_boundary
    path=short_history_path(1)
    consumed=[]
    source=object()
    async def visit(original):
        assert original is path
        return source
    async def settle():pass
    checks=NS(short_learning=[],short_states=lambda:{path.ordinal:(7 if taken else 0,protection)},
        short_consumer=lambda receipt,original,**options:consumed.append((receipt,original,options)))
    # No helper re-steering method: the enclosing real program has already
    # installed its original outcome before asking for direction stability.
    await _mixed_boundary(NS(checks=checks,visit=visit,short_settle=settle),path,taken=taken)
    assert consumed==[(source,path,dict(taken=taken))]


def test_shared_base_learning_makes_later_correct_feedback_neutral_without_stopping_direction():
    state=ProtectionState(4,0)
    states=[]
    for base in (0,0,1,1):
        state=state.feedback(predicted=1,base=base,actual=1)
        states.append((state.counter,state.useful))
    assert states==[(5,1),(6,2),(7,2),(7,2)]


@pytest.mark.parametrize('taken,counter',((True,3),(False,4)))
async def test_upper_protection_cannot_excuse_an_unlearned_mixed_direction(taken,counter):
    from bpuverify.bpu.case.history_working_set import _mixed_boundary
    path=short_history_path(1)
    async def visit(original):return object()
    async def settle():pass
    def reject(expected,actual,point):
        assert expected==actual,'declared direction never learned'
    checks=NS(short_learning=[],short_states=lambda:{path.ordinal:(counter,3)},check=reject,
        short_consumer=lambda *args,**options:pytest.fail('wrong direction received consumer credit'))
    with pytest.raises(AssertionError,match='declared direction never learned'):
        await _mixed_boundary(NS(checks=checks,visit=visit,short_settle=settle),path,taken=taken)


@pytest.mark.parametrize('profile',SHORT_MIXED_PROFILES)
def test_mixed_incoming_program_has_real_independent_consumers_and_nonmasking_teachers(profile):
    p=ShortMixedWorkingSetProgram(profile)
    assert len(p.positives)==15 and len(p.mixed)==7
    assert p.selected[0] not in p.mixed
    assert p.selected[0]==p.learning_order[0 if profile.startswith('oldest') else -1]
    originals={path.read_indices[1] for path in p.paths}
    for path in p.positives:
        companions=tuple(short_learning_path(path.ordinal,older)
            for older in (*SHORT_TURNAROUND_PATHS,*SHORT_RESTORATION_PATHS))
        assert len({item.read_indices[1] for item in companions})==8
        assert not originals & {item.read_indices[1] for item in companions}
        assert {(item.read_indices[0],item.tags[0]) for item in companions}=={(path.read_indices[0],path.tags[0])}
        assert all(max(item.tags)<256 for item in companions)  # Full tags, never masked to eight bits.
        assert max(map(main_capacity,companions))<=4
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']


@pytest.mark.parametrize('ordinal',(1,2,15))
@pytest.mark.parametrize('older',(15,8,14))
def test_autonomous_model_proves_mixed_learning_ancestry_before_any_DUT(ordinal,older):
    path=short_learning_path(ordinal,older)
    _,ahead,short=steady_model_source(path)
    assert short.read.indices==path.read_indices
    assert tuple(short.context.folds[index] for index in FEATURES)==path.tag_features
    assert (ahead.read.bank,ahead.read.row)==path.ahead_key


@pytest.mark.parametrize('profile',SHORT_MIXED_PROFILES)
def test_mixed_direction_round_trip_uses_distinct_originals_and_preserves_all_other_experience(profile):
    p=ShortMixedWorkingSetProgram(profile)
    states={path.ordinal:ProtectionLedger(counter=0,protection=3) for path in p.positives}
    owner=0
    for path,taken in (*( (path,True) for path in p.mixed), (p.selected[0],True),(p.selected[0],False)):
        saved={key:(value.counter,value.protection) for key,value in states.items() if key!=path.ordinal}
        ledger=states[path.ordinal]
        plan=p.reversal(path,counter=ledger.counter,protection=ledger.protection,taken=taken)
        assert len(plan)==4
        for _,before,after in plan:
            event=ledger.apply(owner,taken,'penalty');owner+=1
            assert (event.counter_before,event.before)==(before.counter,before.useful)
            assert (event.counter_after,event.after)==(after.counter,after.useful)
        for _ in range(4):ledger.apply(owner,taken,'reward');owner+=1
        assert (ledger.counter,ledger.protection)==(7 if taken else 0,3)
        assert saved=={key:(value.counter,value.protection) for key,value in states.items() if key!=path.ordinal}
    assert {key for key,value in states.items() if value.counter>=4}=={path.ordinal for path in p.mixed}


@pytest.mark.parametrize('missing',SHORT_MIXED_RULES)
def test_mixed_short_lifetime_never_publishes_an_incomplete_program(missing):
    p=ShortMixedWorkingSetProgram(SHORT_MIXED_PROFILES[0])
    coverage=ShortMixedPathCoverage(p)
    checks=ShortMixedPathChecks(p,coverage)
    checks.pipeline=NS(raise_failure=lambda:None,current_event=None)
    checks.checkpoint=lambda:None
    checks.completed=set(SHORT_MIXED_RULES)-{missing}
    with pytest.raises(AssertionError,match='all mixed short-experience obligations'):
        checks.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('tag','position','counter','valid','all-cached'))
def test_mixed_short_storage_requires_actual_payload_and_real_shadow_turnover(fault):
    p=ShortMixedWorkingSetProgram(SHORT_MIXED_PROFILES[0])
    checks=ShortMixedPathChecks(p,ShortMixedPathCoverage(p))
    checks.pipeline=NS(current_event=NS(tick=100))
    checks.storage_layout=(8,4,3,1)
    checks.short_ledgers={path.ordinal:ProtectionLedger(counter=7 if path in p.mixed else 0,protection=3)
        for path in p.positives}
    words=[(((((1<<8)|path.tags[0])<<4|2)<<3|checks.short_ledgers[path.ordinal].counter)<<1)
        for path in p.positives]
    cells=tuple(dict(valid=True,index=path.read_indices[0]) for path in p.positives)
    if fault!='all-cached':words[0]^={'tag':1<<8,'position':1<<4,'counter':1<<1,'valid':1<<16}[fault]
    # Physical capacity must come from the binding, not an arbitrary oversized mock.
    if fault!='all-cached':cells=cells[:8]
    checks.native_storage=dict(words=tuple(words),cells=cells)
    with pytest.raises(AssertionError):checks.check_storage('fault-control')
    assert not checks.storage_checks


@pytest.mark.parametrize('profile',tuple(PROFILES))
def test_declared_lifetime_is_capacity_safe_and_has_distinct_real_history_identities(profile):
    p = HistoryWorkingSetProgram(profile)
    assert len({path.read_indices[1] for path in p.paths}) == len(p.paths)
    assert len({path.ahead_key for path in p.paths}) == (16 if profile=='capacity-reverse' else 1)
    assert len(p.positives)+len(p.helpers) == len(p.paths)
    assert max(max(path.tags) for path in p.paths) < 256
    assert max(main_capacity(path) for path in p.paths) <= 4
    assert all(path.edges()[-1].target == ANCHOR for path in p.paths)
    assert all(len({pc for pc in path.pcs}) == 8 for path in p.paths)
    assert all(edge.pc <= edge.cfi_pc < edge.pc+16 for path in p.paths for edge in path.edges())
    assert all(p.helper_for(path).tail_variant == path.tail_variant for path in p.paths)
    assert all(p.helper_for(path).ahead_key == path.ahead_key for path in p.paths)
    assert all(path in p.positives for path in p.selected)
    assert p.paths is p.paths and p.positives is p.positives
    assert all(path.word & 31 == 0 for path in p.helpers)
    assert {path.read_indices[0] for path in p.short_consumers} == {path.read_indices[0] for path in p.paths}
    if profile == 'capacity-reverse':
        assert len(p.paths) == 512 and len(p.positives) == 496 and len(p.short_prerequisites) == 32


@pytest.mark.parametrize('profile',SHORT_PROFILES)
def test_incoming_short_program_has_distinct_owners_without_a_physical_matrix(profile):
    p=ShortWorkingSetProgram(profile)
    assert len(p.positives)==(7 if profile.startswith('retained-') else 15)
    assert len({path.read_indices[0] for path in p.paths})==len(p.paths)
    assert len({path.read_indices[1] for path in p.paths})==len(p.paths)
    assert len({path.ahead_key for path in p.paths})==1
    assert all(0<=path.tags[0]<32 for path in p.paths)
    assert len({path.tail_variant for path in p.paths})==len(p.paths)
    assert max(main_capacity(path) for path in p.paths)<=4
    assert p.selected[0] == (p.positives[0] if profile.endswith('-oldest') else p.positives[-1])
    assert p.helper.read_indices[0] not in {path.read_indices[0] for path in p.positives}
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']


@pytest.mark.parametrize('ordinal',(0,1,7,8,15))
def test_full_autonomous_model_proves_new_short_incoming_ancestry(ordinal):
    path=short_history_path(ordinal)
    token,ahead,short=steady_model_source(path)
    assert short.read.indices==path.read_indices
    assert tuple(short.context.folds[index] for index in FEATURES)==path.tag_features
    assert (ahead.read.bank,ahead.read.row)==path.ahead_key


@pytest.mark.parametrize('missing',SHORT_RULES)
def test_short_retention_cannot_close_without_actual_memory_and_all_consumers(missing):
    p=ShortWorkingSetProgram(SHORT_PROFILES[0])
    coverage=ShortPathRetentionCoverage(p)
    checks=ShortPathRetentionChecks(p,coverage)
    checks.pipeline=NS(raise_failure=lambda:None,current_event=None)
    checks.checkpoint=lambda:None
    checks.completed=set(SHORT_RULES)-{missing}
    with pytest.raises(AssertionError,match='all short retention obligations'):
        checks.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('tag','counter','valid'))
def test_native_short_SRAM_is_not_excused_by_a_correct_shadow_value(fault):
    p=ShortWorkingSetProgram(SHORT_PROFILES[0])
    checks=ShortPathRetentionChecks(p,ShortPathRetentionCoverage(p))
    checks.pipeline=NS(current_event=None)
    checks.storage_layout=(8,4,3,1)
    checks.short_ledgers={path.ordinal:ProtectionLedger(counter=0,protection=3) for path in p.positives}
    def word(path):return ((((1<<8)|path.tags[0])<<4|2)<<3)<<1
    words=[word(path) for path in p.positives]
    if fault=='tag':words[0]^=1<<8
    elif fault=='counter':words[0]|=1<<1
    else:words[0]&=~(1<<16)
    checks.native_storage=dict(words=tuple(words),cells=tuple(dict(valid=1,index=path.read_indices[0]) for path in p.paths))
    with pytest.raises(AssertionError,match='actual SRAM retains'):
        checks.check_storage('fault-control')
    assert not checks.storage_checks


def steady_model_source(path):
    # Synthetic semantic setup ONLY: this fixture never opens a DUT. Main
    # entries are declared instructions, not sampled hardware or legacy data.
    model = PipelineReference(EarlyDirectionSources())
    enabled = (True,True,True,False,False,False,False)
    for _ in range(4):model.advance(Events(ANCHOR,enabled=enabled))
    edges = ((ANCHOR,12,path.pcs[0]),)+tuple((edge.pc,edge.position,edge.target) for edge in path.edges())
    ways = Counter()
    for pc,pos,destination in edges:
        address = (pc&~15)+(pos//16)*16
        alignment,bank,row = coordinate(address)
        way = ways[alignment,bank,row]
        ways[alignment,bank,row] += 1
        model.sources.main.memory[alignment,bank,row,way] = MainEntry(
            tag(address),pos%16,3,0,Target.encode(address,destination))
        model.sources.main.counters[alignment,bank,row,way] = 2
    samples,early_identities = [],set()
    for _ in range(180):
        cycle = model.advance(Events(ANCHOR,enabled=enabled,initialization_complete=True))
        token = cycle.metadata
        if token is not None and token.early.branch.taken:
            early_identities.add(token.pc)
        if token is None or token.pc != ANCHOR:continue
        ahead = model.sources.snapshot(token).frame
        short = model.sources.short_snapshot(token).prediction.frame
        if ahead is not None and short is not None:
            samples.append((token,ahead,short))
    assert len(early_identities) == 9 and samples
    return samples[-1]


@pytest.mark.parametrize('ordinal',(0,1,2,4,8,16,32,64,128,256,511))
def test_complete_autonomous_model_proves_index_tag_and_current_history_are_distinct_owners(ordinal):
    path = history_path(ordinal)
    token,ahead,short = steady_model_source(path)
    assert token.early.branch.taken and token.early.branch.target == path.pcs[0]
    assert (ahead.read.bank,ahead.read.row) == path.ahead_key
    assert short.read.indices == path.read_indices
    assert tuple(short.context.folds[i] for i in FEATURES) == path.tag_features
    if ordinal == 0:
        assert tuple(token.history.folds()[i] for i in FEATURES) != path.tag_features


def test_outcome_ledger_retains_other_paths_across_reward_bound_hold_error_and_recovery():
    p = HistoryWorkingSetProgram('turnover-reverse')
    ledger = HistoryLearningLedger(p)
    a,b = p.positives[:2]
    assert ledger.allocate(a,taken=True).useful == 2
    ledger.allocate(b,taken=True)
    saved = deepcopy(ledger.states[b.ordinal])
    assert ledger.feedback(a,predicted=1,base=0,actual=1).useful == 3
    assert ledger.feedback(a,predicted=1,base=0,actual=1).useful == 3
    assert ledger.feedback(a,predicted=1,base=1,actual=0).useful == 2
    assert ledger.feedback(a,predicted=1,base=0,actual=1).useful == 3
    assert ledger.states[b.ordinal] == saved
    assert ledger.transitions == dict(allocate=2,reward=2,hold=1,penalty=1)


@pytest.mark.parametrize('fault',('double-allocation','unadmitted-feedback','implicit-direction','foreign-path','helper'))
def test_logical_ledger_rejects_missing_or_duplicated_ownership(fault):
    p = HistoryWorkingSetProgram('turnover-forward')
    ledger = HistoryLearningLedger(p)
    path = p.positives[0]
    if fault == 'double-allocation':ledger.allocate(path,taken=True)
    with pytest.raises(ValueError):
        if fault == 'unadmitted-feedback':ledger.feedback(path,predicted=1,base=0,actual=1)
        elif fault == 'foreign-path':ledger.allocate(history_path(511),taken=True)
        elif fault == 'helper':ledger.allocate(p.helper,taken=True)
        else:ledger.allocate(path,taken=1 if fault == 'implicit-direction' else True)


@pytest.mark.parametrize('fault',('tag','position','confidence','protection'))
def test_retention_checkpoint_rejects_a_wrong_noncurrent_identity(fault):
    p = HistoryWorkingSetProgram('turnover-forward')
    checks = HistoryWorkingSetChecks(p,HistoryWorkingSetCoverage(p))
    path = p.positives[0]
    checks.ledger.allocate(path,taken=True)
    short = UtageReference()
    values = dict(valid=True,tag=path.tags[1],position=POSITION,counter=4)
    if fault == 'tag':values['tag'] ^= 1
    elif fault == 'position':values['position'] -= 1
    elif fault == 'confidence':values['counter'] = 5
    short.memory[1][path.read_indices[1]] = Entry(**values)
    short.useful[1][path.read_indices[1]] = 1 if fault == 'protection' else 2
    checks.pipeline = NS(model=NS(sources=NS(short=short)),current_event=NS(tick=100),raise_failure=lambda:None)
    with pytest.raises(AssertionError,match='survives other histories'):checks.checkpoint()
    assert checks.coverage.groups['checked'].coverage == 0


def test_incomplete_lifetime_cannot_claim_checked_obligations():
    p = HistoryWorkingSetProgram('turnover-forward')
    checks = HistoryWorkingSetChecks(p,HistoryWorkingSetCoverage(p))
    checks.pipeline = NS(model=NS(sources=NS(short=UtageReference())),current_event=NS(tick=100),raise_failure=lambda:None)
    with pytest.raises(AssertionError):checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_scenario_expresses_history_lifetimes_without_raw_signals_or_scheduler_choreography():
    tree = ast.parse(Path('bpuverify/bpu/case/history_working_set.py').read_text())
    names = {node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
    names |= {node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
    assert not names & {'RisingEdge','FallingEdge','ClockCycles','gather','create_task','get_','set_'}
    text = Path('bpuverify/bpu/model/history_working_set.py').read_text()
    assert not any(word in text for word in ('lcov','memory_signal','native_rows','toffee'))


@pytest.mark.parametrize('position',(2,10,12))
async def test_preparation_recovers_original_source_not_new_table_contents(position):
    env = object.__new__(HistoryWorkingSetEnv)
    env.pc = ANCHOR
    env.program = HistoryWorkingSetProgram('turnover-forward')
    env.source = object()
    calls = []
    result = object()
    async def go(source,edge):
        assert source is env.source
        calls.append(('recovery',edge))
    async def window():
        calls.append(('window',))
        return result
    env.go,env.window = go,window
    assert await env.fresh_anchor(position) is result
    assert [call[0] for call in calls] == ['recovery','window']
    edge = calls[0][1]
    assert (edge.pc,edge.target,edge.position,edge.kind) == (
        ANCHOR,env.program.helper.pcs[0],position,3 if position == 12 else 1)


@pytest.mark.parametrize('stale',(False,True))
async def test_preparation_arms_target_before_recovery_and_retires_only_after_its_actual_window(stale):
    env = object.__new__(HistoryWorkingSetEnv)
    env.program = HistoryWorkingSetProgram('turnover-forward')
    edge = env.program.helper.edges()[0]
    source = NS(prediction=NS(start_pc=edge.pc),meta=NS(resolve={'original':'resolve'},redirect={'original':'redirect'}),meta_tick=20)
    following = NS(prediction_tick=21 if stale else 24)
    token = NS(history=NS(taken_edges=8))
    calls = []
    accepted = object()
    def arm(path,position,*,pc):
        assert path is None and position is None and pc == edge.target
        calls.append('arm-target')
        return accepted
    async def redirect(tx):
        assert tx.meta is source.meta.redirect
        assert calls == ['arm-target']
        calls.append('recovery-accept')
        return 22
    async def window(pc,**kwargs):
        assert pc == edge.target and kwargs == dict(accepted=accepted)
        calls.append('target-window-closed')
        return following
    def check(expected,actual,label):assert expected == actual,label
    env.checks = NS(check=check,path_recoveries=0,redirect_receipts=[],open_window=arm)
    env.checker = NS(model=NS(history=NS(taken_edges=8)),source_token=lambda source:token,
        plan_redirect=lambda *args:None,retire_source=lambda tick:calls.append(('retire',tick)))
    env.agent,env.source_window = NS(redirect=redirect),window
    if stale:
        with pytest.raises(AssertionError,match='younger'):await env.go(source,edge)
    else:assert await env.go(source,edge) is following
    assert calls == ['arm-target','recovery-accept','target-window-closed']+([] if stale else [('retire',20)])
    assert env.checks.path_recoveries == int(not stale)


@pytest.mark.parametrize('changed',(False,True))
async def test_predecessor_executes_declared_instruction_and_only_teaches_changed_target(changed):
    env = object.__new__(HistoryWorkingSetEnv)
    edge = HistoryWorkingSetProgram('turnover-forward').helper.edges()[0]
    source,result = object(),object()
    values = {'0.valid':1,'0.position':edge.position,'0.target':edge.target+int(changed),'0.kind':edge.kind}
    env.checker = NS(source_token=lambda original:NS(lookup=NS(values=lambda:values)))
    calls = []
    async def feedback(original,instruction):
        assert original is source and instruction is edge
        calls.append('teach changed instruction')
    async def go(original,instruction):
        assert original is source and instruction is edge
        calls.append('execute actual edge')
        return result
    env.feedback,env.go = feedback,go
    assert await env.predecessor(source,edge) is result
    assert calls == (['teach changed instruction'] if changed else [])+['execute actual edge']


@pytest.mark.parametrize('counter',(4,5,6,7))
@pytest.mark.parametrize('useful',(0,3))
def test_direction_plan_is_frozen_before_driving_and_crosses_the_behavior_boundary(counter,useful):
    program = HistoryWorkingSetProgram('turnover-forward')
    ledger = HistoryLearningLedger(program)
    path,other = program.positives[:2]
    ledger.states[path.ordinal] = ProtectionState(counter,useful)
    ledger.states[other.ordinal] = ProtectionState(7,3)
    before = deepcopy(ledger.state())
    expected = ledger.reversal(path,taken=False)
    assert ledger.state() == before, 'declaring expected outcomes must not train the reference'
    assert len(expected) == counter-3 and not expected[-1].taken
    assert all(state.taken for state in expected[:-1])
    for state in expected:
        old = ledger.states[path.ordinal]
        assert ledger.feedback(path,predicted=old.taken,base=0,actual=0) == state
        assert ledger.states[other.ordinal] == ProtectionState(7,3)


def test_selected_history_can_publicly_reverse_and_restore_without_changing_another_history():
    program = HistoryWorkingSetProgram('turnover-forward')
    ledger = HistoryLearningLedger(program)
    selected,other = program.positives[:2]
    for path in (selected,other):
        ledger.allocate(path,taken=True)
        for _ in range(3):ledger.feedback(path,predicted=1,base=0,actual=1)
    for state in ledger.reversal(selected,taken=False):
        old = ledger.states[selected.ordinal]
        assert ledger.feedback(selected,predicted=old.taken,base=0,actual=0) == state
    assert not ledger.states[selected.ordinal].taken and ledger.states[other.ordinal].taken
    ledger.feedback(selected,predicted=0,base=0,actual=0)
    old_directions = []
    for _ in range(5):
        old = ledger.states[selected.ordinal]
        old_directions.append(old.taken)
        ledger.feedback(selected,predicted=old.taken,base=0,actual=1)
    assert old_directions == [0,0,1,1,1]
    assert ledger.states[selected.ordinal] == ledger.states[other.ordinal] == ProtectionState(7,3)


@pytest.mark.parametrize('fault',('none','wrong-conditional','wrong-fallback','wrong-target','wrong-original-echo','wrong-provider'))
def test_correct_internal_direction_cannot_hide_wrong_public_branch_selection(fault):
    program = HistoryWorkingSetProgram('turnover-forward')
    checks = HistoryWorkingSetChecks(program,HistoryWorkingSetCoverage(program))
    path = program.selected[0]
    taken = fault == 'wrong-fallback'
    position = 10 if taken else 12
    actual_position = 10 if fault == 'wrong-conditional' else 12 if fault == 'wrong-fallback' else position
    source = NS(prediction_tick=30,meta_tick=34,
        prediction=NS(start_pc=ANCHOR,position=actual_position,target=program.helper.pcs[0]+int(fault=='wrong-target'),taken=1),
        meta=NS(perf=NS(s1_position=position-int(fault=='wrong-original-echo'),s1_target=program.helper.pcs[0])))
    checks.expected_results[path.ordinal] = taken
    checks.provider = lambda *args:(1,4 if taken else 3,not taken if fault=='wrong-provider' else taken)
    if fault == 'none':
        checks.direction(source,path,taken=taken,phase='mixed')
        assert checks.mixed_consumers == {path.ordinal:False}
        assert checks.public_consumers['mixed'][path.ordinal]['position'] == 12
    else:
        with pytest.raises(AssertionError):checks.direction(source,path,taken=taken,phase='mixed')
        assert not checks.mixed_consumers and not checks.public_consumers['mixed']
    assert checks.coverage.groups['checked'].coverage == 0


def test_declaring_one_path_outcome_does_not_rewrite_the_model_or_another_history():
    program = HistoryWorkingSetProgram('turnover-forward')
    checks = HistoryWorkingSetChecks(program,HistoryWorkingSetCoverage(program))
    selected,other = program.positives[:2]
    for path in (selected,other):checks.ledger.allocate(path,taken=True)
    before = deepcopy(checks.ledger.state())
    checks.declare_result(selected,False)
    assert checks.ledger.state() == before
    assert checks.expected_results == {selected.ordinal:False}
    with pytest.raises(ValueError):checks.declare_result(other,0)


@pytest.mark.parametrize('protection',(0,1,2,3))
async def test_restore_separates_public_direction_recovery_from_earning_protection(protection):
    program = HistoryWorkingSetProgram('turnover-forward')
    path = program.selected[0]
    env = object.__new__(HistoryWorkingSetEnv)
    states = {path.ordinal:ProtectionState(2,protection)}
    calls = []
    returned = []
    def check(expected,actual,label):assert expected == actual,label
    def declare(original,taken):
        assert original is path and taken is True
        calls.append('declare-T')
    def direction(source,original,**kwargs):
        assert source is returned[-1] and original is path
        assert kwargs == dict(taken=True,phase='restored')
        calls.append('public-T')
    env.checks = NS(declare_result=declare,ledger=NS(states=states),check=check,
                    direction=direction,recovered=set(),maintenance=NS(failures=NS(ages=0)))
    async def positive(original,*,require_upper):
        assert original is path and require_upper is False
        calls.append('actual-T-guidance')
        before = states[path.ordinal]
        states[path.ordinal] = ProtectionState(5,protection) if len(returned)==0 else ProtectionState(
            min(7,before.counter+1),before.useful+1)
        result = object()
        returned.append(result)
        return result
    env.positive = positive
    await env.restore(path)
    assert len(returned) == 1+3-protection
    assert calls[0] == 'declare-T' and calls[-1] == 'public-T'
    assert states[path.ordinal].useful == 3 and env.checks.recovered == {path.ordinal}


@pytest.mark.parametrize('initial',(0,1,2,3))
@pytest.mark.parametrize('taken',(False,True))
async def test_main_preparation_sends_only_desired_outcomes_and_stops_when_direction_is_ready(initial,taken):
    env = object.__new__(HistoryWorkingSetEnv)
    env.pc = ANCHOR
    env.program = HistoryWorkingSetProgram('turnover-forward')
    env.source = object()
    state = NS(counter=initial)
    calls = []
    def direction(source,position):
        assert source is env.source and position == POSITION
        return state.counter >= 2
    async def feedback(source,edge,**kwargs):
        assert source is env.source and edge.position == POSITION
        assert kwargs == dict(taken=taken,mispredict=True)
        calls.append('actual-T' if taken else 'actual-NT')
        state.counter += 1 if taken else -1
    async def fresh(position):
        assert position == (POSITION if taken else 12)
        calls.append('fresh-original')
        env.source = object()
    env.main_direction,env.feedback,env.fresh_anchor = direction,feedback,fresh
    await env.guide(POSITION,taken=taken,later=12)
    count = max(0,2-initial) if taken else max(0,initial-1)
    assert len(calls) == 2*count
    assert (state.counter>=2) is taken


@pytest.mark.parametrize('taken',(0,1,None))
async def test_main_preparation_rejects_implicit_direction_without_accessing_an_agent(taken):
    env = object.__new__(HistoryWorkingSetEnv)
    with pytest.raises(ValueError):await env.guide(POSITION,taken=taken,later=12)
