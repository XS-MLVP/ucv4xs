"""Pure protocol/model fault controls never provide BPU-INT-103 credit."""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from toffee import CoverageDatabase

from suites.frontend.bpu.bpu.checker.short_context_ownership import ShortContextChecks
from suites.frontend.bpu.bpu.case import short_context_ownership as CASE
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortContextCoverage
from suites.frontend.bpu.bpu.env.history_working_set import HistoryWorkingSetEnv
from suites.frontend.bpu.bpu.env.short_context_ownership import ShortContextEnv
from suites.frontend.bpu.bpu.model.early_direction_sources import EarlyDirectionSources
from suites.frontend.bpu.bpu.model.early_protection import ProtectionLedger
from suites.frontend.bpu.bpu.model.history_working_set import FEATURES
from suites.frontend.bpu.bpu.model.pipeline import Events, PipelineReference
from suites.frontend.bpu.bpu.model.short_context_ownership import (
    OWNERS, OLDER_PATHS, PROFILES, RULES, ShortContextProgram, path)
from suites.frontend.bpu.mbtb.model.semantic import Entry, Target, coordinate, tag

pytestmark = pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize('branch', OWNERS)
@pytest.mark.parametrize('older', (*OLDER_PATHS,15,14))
def test_autonomous_composed_model_reproduces_declared_real_path_ancestry(branch, older):
    declared = path(branch,older)
    model = PipelineReference(EarlyDirectionSources())
    enabled = (True,True,True,False,False,False,False)
    for _ in range(4):model.advance(Events(declared.branch_pc,enabled=enabled))
    edges = ((declared.branch_pc,12,declared.pcs[0]),)+tuple(
        (edge.pc,edge.position,edge.target) for edge in declared.edges())
    ways = Counter()
    for pc,position,destination in edges:
        address = (pc & ~15) + (position//16)*16
        alignment,bank,row = coordinate(address)
        way = ways[alignment,bank,row]
        ways[alignment,bank,row] += 1
        assert way < 4, 'the declared program must fit real MainBTB associativity'
        # Instructions are declared pure-model inputs, never observed SRAM.
        model.sources.main.memory[alignment,bank,row,way] = Entry(
            tag(address),position%16,3,0,Target.encode(address,destination))
        model.sources.main.counters[alignment,bank,row,way] = 2
    samples = []
    for _ in range(180):
        cycle = model.advance(Events(declared.branch_pc,enabled=enabled,initialization_complete=True))
        token = cycle.metadata
        if token is not None and token.pc == declared.branch_pc:
            frame = model.sources.short_snapshot(token).prediction.frame
            if frame is not None:samples.append(frame)
    assert samples
    frame = samples[-1]
    assert frame.read.indices == declared.read_indices
    assert tuple(frame.context.folds[index] for index in FEATURES) == tuple(
        declared.match_context.folds[index] for index in FEATURES)


from suites.frontend.bpu.bpu.model.short_context_ownership import ShortDirectionProgram,DIRECTION_PROFILES,DIRECTION_RULES
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortDirectionCoverage
from suites.frontend.bpu.bpu.checker.short_context_ownership import ShortDirectionChecks


@pytest.mark.parametrize('profile',DIRECTION_PROFILES)
def test_short_direction_program_keeps_learning_companions_out_of_original_consumers(profile):
    p=ShortDirectionProgram(profile)
    assert p.selected in OWNERS and set(p.learning_order)==set(OWNERS)
    plan=p.reversal(p.selected,counter=0,protection=3,taken=True)
    assert [after.counter for _,_,after in plan]==[1,2,3,4]
    restore=p.reversal(p.selected,counter=7,protection=3,taken=False)
    assert [after.counter for _,_,after in restore]==[6,5,4,3]
    original={item.read_indices[1] for item in p.paths if item.branch==p.selected}
    teaching=[item for item,_,_ in (*plan,*restore)]
    assert len({item.read_indices[1] for item in teaching})==8
    assert not original & {item.read_indices[1] for item in teaching}
    assert len({item.short_identity for item in teaching})==1
    assert teaching[0].short_identity==p.storage_paths[OWNERS.index(p.selected)].short_identity
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']


def test_short_independent_outcome_ledger_completes_both_direction_bounds_and_restores_only_selected():
    for profile in DIRECTION_PROFILES:
        p=ShortDirectionProgram(profile)
        chosen=ProtectionLedger(counter=0,protection=3)
        other=ProtectionLedger(counter=0,protection=3)
        owner=0
        for taken in (True,False):
            for _,before,after in p.reversal(p.selected,counter=chosen.counter,protection=chosen.protection,taken=taken):
                actual=chosen.apply(owner,taken,'penalty');owner+=1
                assert (actual.counter_before,actual.before)==(before.counter,before.useful)
                assert (actual.counter_after,actual.after)==(after.counter,after.useful)
            for _ in range(4):
                chosen.apply(owner,taken,'reward');owner+=1
            assert (chosen.counter,chosen.protection)==(7 if taken else 0,3)
            assert (other.counter,other.protection)==(0,3)


def test_short_direction_cannot_publish_checked_before_every_declared_obligation():
    p=ShortDirectionProgram(DIRECTION_PROFILES[0])
    for missing in DIRECTION_RULES:
        coverage=ShortDirectionCoverage(p)
        checks=ShortDirectionChecks(p,coverage)
        checks.pipeline=NS(current_event=None,raise_failure=lambda:None)
        checks.completed=set(DIRECTION_RULES)-{missing}
        with pytest.raises(AssertionError,match='every short-direction lifetime'):
            checks.finish_direction()
        assert coverage.groups['checked'].coverage==0


def test_actual_short_direction_SRAM_must_match_the_independent_record_not_just_cached_prediction():
    p=ShortDirectionProgram(DIRECTION_PROFILES[0])
    for fault in ('tag','position','counter','valid'):
        checks=ShortDirectionChecks(p,ShortDirectionCoverage(p))
        checks.pipeline=NS(current_event=NS(tick=100))
        checks.storage_layout=(8,4,3,1)
        checks.ledgers={branch:ProtectionLedger(counter=4 if branch==p.selected else 0,protection=3) for branch in OWNERS}
        words=[]
        for item in p.storage_paths:
            state=checks.ledgers[item.branch]
            words.append(((((1<<8)|item.tags[0])<<4|2)<<3|state.counter)<<1)
        words[0]^={'tag':1<<8,'position':1<<4,'counter':1<<1,'valid':1<<16}[fault]
        checks.native_storage=dict(words=tuple(words),cells=())
        with pytest.raises(AssertionError,match='actual SRAM preserves'):
            checks.check_storage('fault-control')
        assert not checks.storage_checks


@pytest.mark.parametrize('profile', PROFILES)
def test_learning_only_paths_cannot_mask_either_original_short_consumer(profile):
    program = ShortContextProgram(profile)
    for branch in OWNERS:
        originals = tuple(item for item in program.paths if item.branch==branch)
        penalty, helper = program.penalty(branch),program.helper(branch)
        assert penalty.short_identity == originals[0].short_identity == originals[1].short_identity
        assert penalty.read_indices[1] not in {item.read_indices[1] for item in originals}
        assert helper.read_indices[0] not in {item.read_indices[0] for item in program.paths}
        assert all(value < 256 for value in (*penalty.tags,*helper.tags))


def complete_checks():
    program = ShortContextProgram(PROFILES[0])
    coverage = ShortContextCoverage(program)
    checks = ShortContextChecks(program,coverage)
    checks.pipeline = NS(current_event=None,raise_failure=lambda:None)
    checks.ledgers = {branch:ProtectionLedger(counter=0,protection=2) for branch in OWNERS}
    checks.penalty_confirmed_tick = 100
    checks.consumers = [dict(phase='final-consumers',branch=item.branch,older_path=item.older_path,
        source_id=index,query_tick=102+index*2,provider=0) for index,item in enumerate(program.paths)]
    source = NS(meta=NS(resolve=dict(original=1),redirect=dict(original=2)))
    checks.originals.append((source,deepcopy(source.meta.resolve),deepcopy(source.meta.redirect)))
    for rule in RULES:
        if rule != 'immutable-original-snapshots':checks.mark(rule)
    return checks,coverage


def checked_counts(coverage):
    group, = [item for item in CoverageDatabase(coverage.groups.values()).report()['groups']
              if item['instance'].endswith('.checked')]
    return group['points'][0]['counts']


def test_only_complete_lifetime_publishes_its_own_profile():
    checks,coverage = complete_checks()
    assert not any(checked_counts(coverage).values())
    checks.finish_sharing()
    counts = checked_counts(coverage)
    assert {name:count for name,count in counts.items() if count} == {
        checks.program.profile+'.'+rule:1 for rule in RULES}
    assert coverage.groups['checked'].coverage == 50
    with pytest.raises(AssertionError):checks.finish_sharing()
    assert checked_counts(coverage) == counts


@pytest.mark.parametrize('fault', ('missing-branch','pending-actual-state','missing-consumer',
    'duplicate-consumer','duplicate-source','stale-consumer','long-provider-substitute',
    'unconfirmed-correction','mutated-original'))
def test_incomplete_or_wrong_owner_lifetime_gets_no_checked_credit(fault):
    checks,coverage = complete_checks()
    if fault == 'missing-branch': checks.ledgers.pop('right')
    elif fault == 'pending-actual-state': checks.pending_protection = ('left',2,99)
    elif fault == 'missing-consumer': checks.consumers.pop()
    elif fault == 'duplicate-consumer': checks.consumers.append(deepcopy(checks.consumers[0]))
    elif fault == 'duplicate-source': checks.consumers[1]['source_id'] = checks.consumers[0]['source_id']
    elif fault == 'stale-consumer': checks.consumers[0]['query_tick'] = 100
    elif fault == 'long-provider-substitute': checks.consumers[0]['provider'] = 1
    elif fault == 'unconfirmed-correction': checks.penalty_confirmed_tick = None
    elif fault == 'mutated-original': checks.originals[0][0].meta.resolve['original'] = -1
    with pytest.raises(AssertionError):checks.finish_sharing()
    assert not any(checked_counts(coverage).values())


@pytest.mark.parametrize('missing', tuple(rule for rule in RULES if rule != 'immutable-original-snapshots'))
def test_each_semantic_obligation_is_mandatory_even_with_all_consumers(missing):
    checks,coverage = complete_checks()
    checks.completed.remove(missing)
    with pytest.raises(AssertionError):checks.finish_sharing()
    assert not any(checked_counts(coverage).values())


@pytest.mark.parametrize('pc', (0x40000000,0x40000040))
async def test_main_guidance_feedback_uses_the_selected_branch_not_a_global_anchor(pc):
    edges = []
    async def nothing(*args,**kwargs):pass
    async def feedback(source,edge,**kwargs):edges.append(edge)
    view = NS(pc=pc,source=object(),program=NS(helper=NS(pcs=(0x40080020,))),
        pause=nothing,agent=NS(configure_predictors=nothing),guide=nothing,
        has_main=lambda source,position:False,feedback=feedback,fresh_anchor=nothing)
    await HistoryWorkingSetEnv.set_main(view,early=False,target=False)
    assert tuple(edge.pc for edge in edges) == (pc,pc)
    assert tuple(edge.position for edge in edges) == (10,12)


@pytest.mark.parametrize('anchor_pc', (None,0x40000000,0x40000040))
def test_original_default_anchor_is_unchanged_and_other_anchors_are_explicit(anchor_pc):
    observation = NS(checker=NS(model=NS(sources=NS(micro=object()))))
    options = {} if anchor_pc is None else dict(anchor_pc=anchor_pc)
    view = HistoryWorkingSetEnv(None,observation,object(),object(),object(),**options)
    assert view.pc == (0x40000000 if anchor_pc is None else anchor_pc)


async def test_switch_restores_shared_instruction_targets_before_main_can_follow_them():
    program = ShortContextProgram(PROFILES[0])
    calls = []
    new_source = object()
    async def go(source,edge):
        calls.append(('real-recovery',edge.pc,edge.target))
        return new_source
    async def visit(path):
        calls.append(('restore-actual-program',path))
    async def settle():calls.append(('settled',))
    old = NS(program=program.view('left'),pc=program.helper('left').branch_pc,
             source=object(),go=go)
    following = NS(program=program.view('right'),source=object(),visit=visit)
    env = ShortContextEnv(None,None,None,program,None)
    env.views,env.active,env.settle = dict(left=old,right=following),old,settle
    result = await env.select('right')
    assert result is following and result.source is new_source
    assert [call[0] for call in calls] == ['settled','real-recovery','restore-actual-program','settled']
    assert calls[2][1] == program.helper('right')


@pytest.mark.parametrize('failed_exit', (False,True))
async def test_checked_credit_follows_complete_monitor_scope_exit(monkeypatch,failed_exit):
    checks,coverage = complete_checks()
    async def exercise(agent,program,actual_coverage):
        assert actual_coverage is coverage and not any(checked_counts(coverage).values())
        if failed_exit:raise AssertionError('passive scope exit failed')
        return checks
    monkeypatch.setattr(CASE,'_exercise_short_context',exercise)
    if failed_exit:
        with pytest.raises(AssertionError,match='passive scope exit failed'):
            await CASE.check_short_context_ownership(None,checks.program,coverage)
        assert not any(checked_counts(coverage).values())
    else:
        await CASE.check_short_context_ownership(None,checks.program,coverage)
        assert coverage.evidence['status']=='PASS' and coverage.groups['checked'].coverage==50


from suites.frontend.bpu.bpu.model.short_context_ownership import (
    ShortCrossBranchProgram,WORKING_SET_PROFILES,WORKING_SET_RULES,working_set_path)
from suites.frontend.bpu.bpu.checker.short_context_ownership import ShortCrossBranchChecks
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortCrossBranchCoverage
from suites.frontend.bpu.utage.model.semantic import Base as UtageBase,Events as UtageEvents,Source as UtageSource,Feedback as UtageFeedback,UtageReference


@pytest.mark.parametrize('profile',WORKING_SET_PROFILES)
def test_working_set_has_two_branch_groups_beyond_recent_capacity_and_discriminating_real_older_paths(profile):
    p=ShortCrossBranchProgram(profile)
    assert len(p.paths)==14 and len({path.short_identity for path in p.paths})==14
    assert len({path.read_indices[0] for path in (*p.paths,*(p.helper(branch) for branch in OWNERS))})==16
    assert len(p.paths)>8 and {path.branch for path in p.paths}==set(OWNERS)
    assert len(p.mixed)==3 and p.selected_path not in p.mixed
    assert all(item.branch==p.selected for item in p.mixed)
    original={path.read_indices[1] for path in p.paths}
    for item in p.paths:
        teaching=[p.teaching_path(item,older) for older in (15,8,9,10,11,12,13,14)]
        assert all(path.short_identity==item.short_identity for path in teaching)
        assert len({path.read_indices[1] for path in teaching})==8
        assert not original & {path.read_indices[1] for path in teaching}
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']


@pytest.mark.parametrize('profile',WORKING_SET_PROFILES)
def test_same_unchanged_utage_model_derives_shared_storage_learning_and_preserves_all_other_owners(profile):
    p=ShortCrossBranchProgram(profile);model=UtageReference();ledgers={};source_id=0
    def source(path,base):
        event=UtageEvents(read_pc=path.pcs[-1],read_context=path.read_context,select=True,
            pc=path.branch_pc,context=path.match_context,positions=(2,4,8,12),
            bases=(UtageBase(True,2,bool(base),1),UtageBase(),UtageBase(),UtageBase()),advance=True)
        model.advance(event);model.advance(event)
        return model.prediction
    def teach(path,prediction,taken):
        provider=prediction.frame.providers()[0]
        entry=None if provider is None else prediction.frame.read.entries[provider]
        original=UtageSource(True,2,entry is not None,provider or 0,0 if entry is None else entry.counter,
            False if entry is None else entry.counter>=4,prediction.bases[0].taken)
        request=UtageFeedback(path.branch_pc,path.match_context,prediction.frame.read.indices,(original,),2,bool(taken),1)
        model.advance(UtageEvents(feedback=request));model.advance();model.advance()
    def verify():
        for item in p.paths:
            if item.ordinal not in ledgers:continue
            prediction=source(item,not bool(ledgers[item.ordinal].counter>=4))
            assert prediction.frame.providers()[0]==0
            entry=prediction.frame.read.entries[0]
            ledger=ledgers[item.ordinal]
            assert (entry.tag,entry.counter,model.useful[0][item.read_indices[0]])==(item.tags[0],ledger.counter,ledger.protection)
    for branch in p.learning_order:
        for item in p.paths:
            if item.branch!=branch:continue
            cold=source(item,True);assert cold.frame.providers()[0] is None
            teach(item,cold,False);ledger=ledgers[item.ordinal]=ProtectionLedger(counter=3,protection=1)
            for _ in range(3):
                prediction=source(item,True);teach(item,prediction,False)
                ledger.apply(source_id,False,'reward');source_id+=1
    verify()
    for item,taken in [*((item,True) for item in p.mixed),(p.selected_path,True),(p.selected_path,False)]:
        ledger=ledgers[item.ordinal];before={key:(v.counter,v.protection) for key,v in ledgers.items()}
        for teaching,old,new in p.reversal(item,counter=ledger.counter,protection=ledger.protection,taken=taken):
            prediction=source(teaching,not taken);assert prediction.frame.providers()[0]==0
            teach(teaching,prediction,taken);event=ledger.apply(source_id,taken,'penalty');source_id+=1
            assert (event.counter_before,event.before,event.counter_after,event.after)==(old.counter,old.useful,new.counter,new.useful)
        for _ in range(3):
            prediction=source(item,not taken);teach(item,prediction,taken)
            ledger.apply(source_id,taken,'reward');source_id+=1
        assert {key:value for key,value in before.items() if key!=item.ordinal}=={
            key:(value.counter,value.protection) for key,value in ledgers.items() if key!=item.ordinal}
        verify()
    assert all((ledger.counter>=4)==(owner in {path.ordinal for path in p.mixed}) for owner,ledger in ledgers.items())


def complete_working_set_checks(profile=WORKING_SET_PROFILES[0]):
    p=ShortCrossBranchProgram(profile);coverage=ShortCrossBranchCoverage(p);checks=ShortCrossBranchChecks(p,coverage)
    checks.pipeline=NS(current_event=NS(tick=100),raise_failure=lambda:None)
    mixed={path.ordinal for path in p.mixed}
    checks.ledgers={path.ordinal:ProtectionLedger(counter=7 if path.ordinal in mixed else 0,protection=2) for path in p.paths}
    owner=0
    for phase,positive in (('initial',set()),('mixed',mixed),('turned',mixed|{p.selected_path.ordinal}),('final',mixed)):
        for item in p.paths:
            taken=item.ordinal in positive
            checks.consumers.append(dict(phase=phase+'-working-set-consumers',branch=item.branch,path=item.ordinal,
                expected_taken=taken,provider=0,counter=7 if taken else 0,source_id=owner,query_tick=200+owner*2))
            owner+=1
    checks.storage_checks=[dict(phase=phase,tick=100,uncached_paths=[path.ordinal for path in p.paths]) for phase in ('mixed','turned','final')]
    checks.direction_changes=[dict(owner=1000+index) for index in range(20)]
    original=NS(meta=NS(resolve=dict(value=1),redirect=dict(value=2)))
    checks.originals=[(original,deepcopy(original.meta.resolve),deepcopy(original.meta.redirect))]
    for rule in WORKING_SET_RULES:checks.mark(rule)
    return checks,coverage


@pytest.mark.parametrize('profile',WORKING_SET_PROFILES)
def test_only_complete_cross_branch_working_set_credits_its_own_program(profile):
    checks,coverage=complete_working_set_checks(profile)
    checks.finish_working_set()
    assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):checks.finish_working_set()


@pytest.mark.parametrize('missing',WORKING_SET_RULES)
def test_no_cross_branch_working_set_credit_with_any_missing_semantic_requirement(missing):
    checks,coverage=complete_working_set_checks();checks.completed.remove(missing)
    with pytest.raises(AssertionError):checks.finish_working_set()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-other-branch-owner','pending-learning','missing-one-consumer','duplicate-consumer',
    'duplicate-original','wrong-mixed-owner','long-provider-substitute','wrong-direction','stale-before-SRAM',
    'missing-storage-phase','only-one-branch-uncached','missing-original-change','replayed-original-change','mutated-original'))
def test_incomplete_cross_branch_retention_or_wrong_owner_cannot_publish_checked(fault):
    checks,coverage=complete_working_set_checks()
    if fault=='missing-other-branch-owner':checks.ledgers.pop(513)
    elif fault=='pending-learning':checks.pending_protection=(1,2,99)
    elif fault=='missing-one-consumer':checks.consumers.pop()
    elif fault=='duplicate-consumer':checks.consumers.append(deepcopy(checks.consumers[-1]))
    elif fault=='duplicate-original':checks.consumers[-1]['source_id']=checks.consumers[0]['source_id']
    elif fault=='wrong-mixed-owner':checks.consumers[-1]['expected_taken']=True
    elif fault=='long-provider-substitute':checks.consumers[-1]['provider']=1
    elif fault=='wrong-direction':checks.consumers[-1]['counter']=7
    elif fault=='stale-before-SRAM':checks.consumers[-1]['query_tick']=100
    elif fault=='missing-storage-phase':checks.storage_checks.pop()
    elif fault=='only-one-branch-uncached':
        for row in checks.storage_checks:row['uncached_paths']=[1]
    elif fault=='missing-original-change':checks.direction_changes.pop()
    elif fault=='replayed-original-change':checks.direction_changes[-1]['owner']=checks.direction_changes[0]['owner']
    else:checks.originals[0][0].meta.resolve['value']=99
    with pytest.raises((AssertionError,StopIteration)):checks.finish_working_set()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('valid','tag','position','counter','cached-all-identities'))
def test_cross_branch_storage_evidence_cannot_be_replaced_by_cached_predictions(fault):
    checks,coverage=complete_working_set_checks();p=checks.program
    checks.storage_layout=(8,4,3,1);checks.storage_checks=[]
    words=[(((((1<<8)|path.tags[0])<<4|2)<<3|checks.ledgers[path.ordinal].counter)<<1) for path in p.paths]
    cells=tuple(dict(valid=0,index=0) for _ in range(8))
    if fault=='cached-all-identities':cells=tuple(dict(valid=1,index=path.read_indices[0]) for path in p.paths)
    else:words[-1]^={'valid':1<<16,'tag':1<<8,'position':1<<4,'counter':1<<1}[fault]
    checks.native_storage=dict(words=words,cells=cells)
    with pytest.raises(AssertionError):checks.check_storage('fault-control')
    assert not checks.storage_checks
