"""Independent semantic derivation and rejection controls; no hardware credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from suites.frontend.bpu.bpu.model.short_competition import Program,PROFILES,RULES,incoming
from suites.frontend.bpu.bpu.checker.short_competition import Checks
from suites.frontend.bpu.bpu.coverage.short_competition import Coverage
from suites.frontend.bpu.bpu.model.early_protection import ProtectionLedger
from suites.frontend.bpu.bpu.model.early_aging import allocation
from suites.frontend.bpu.utage.model.semantic import Base,Context,TAG_FOLDS,Events,Source,Feedback,UtageReference

pytestmark=pytest.mark.toffee_functional_coverage(False)


def derive(p):
    c=Checks(p,Coverage(p));model=UtageReference();sources=NS(short=model);saved=[];source_id=0
    c.pipeline=NS(current_event=None,raise_failure=lambda:None)
    def query(path,base):
        event=Events(read_pc=path.pcs[-1],read_context=path.read_context,select=True,
            pc=path.branch_pc,context=path.match_context,positions=(2,4,8,12),
            bases=(Base(True,2,bool(base),1),Base(),Base(),Base()),advance=True)
        model.advance(event);model.advance(event)
        result=model.prediction;saved.append((result,deepcopy(result.frame)))
        return result
    def view(result):
        row=result.values()
        return None if not row['0.hit'] else (row['0.provider'],row['0.counter'],bool(row['0.predicted']))
    def teach(path,original,taken):
        nonlocal source_id
        provider=original.frame.providers()[0]
        entry=None if provider is None else original.frame.read.entries[provider]
        source=Source(True,2,entry is not None,provider or 0,0 if entry is None else entry.counter,
            False if entry is None else entry.counter>=4,original.bases[0].taken)
        request=Feedback(path.branch_pc,path.match_context,original.frame.read.indices,(source,),
            2 if taken else 12,True,1 if taken else 3)
        model.advance(Events(feedback=request));model.advance()
        decision=allocation(request,model.learning.useful)
        model.advance();source_id+=1
        c.learning_effect(request,NS(sequence=source_id),decision,source_id*10)
        c.residents(sources)
        if c.pending_protection is not None:
            branch,expected,_=c.pending_protection
            assert model.useful[0][c.identities[branch].index]==expected
        for key,expected,_ in c.pending_long:assert model.useful[1][key[1]]==expected
        c.pending_protection=None;c.pending_long=[]
    a,b=p.original(p.old),p.original(p.new)
    teach(a,query(a,not p.old_taken),p.old_taken)
    for _ in range(3):teach(a,query(a,not p.old_taken),p.old_taken)
    assert c.states()[p.old]==(7 if p.old_taken else 0,3)
    assert view(query(b,p.old_taken)) is None
    teach(b,query(b,p.old_taken),p.new_taken)
    assert c.active_owner==p.old
    weak=4 if p.new_taken else 3
    fresh=query(b,p.old_taken);assert view(fresh)==(1,weak,p.new_taken)
    teach(b,fresh,p.new_taken)
    c.declared_results[p.old]=p.new_taken
    for number in range(3):
        path=p.release(number)
        expected=c.states()[p.old][0]
        original=query(path,p.old_taken);assert view(original)==(0,expected,p.old_taken)
        teach(path,original,p.new_taken)
    c.declared_results[p.old]=p.old_taken
    for _ in range(3):teach(a,query(a,p.old_taken),p.old_taken)
    assert c.states()[p.old]==(7 if p.old_taken else 0,0)
    before={key:(ledger.counter,ledger.protection) for key,ledger in c.long_records.items()}
    teach(p.admission,query(p.admission,p.old_taken),p.new_taken)
    assert c.active_owner==p.new and c.states()[p.new]==(weak,1)
    assert before=={key:(ledger.counter,ledger.protection) for key,ledger in c.long_records.items()}
    assert view(query(a,p.old_taken)) is None
    assert view(query(p.admission,p.old_taken))==(0,weak,p.new_taken)
    assert view(query(b,p.old_taken))==(1,weak+(1 if p.new_taken else -1),p.new_taken)
    assert view(query(p.release(0),p.old_taken))==(1,weak,p.new_taken)
    assert all(source.frame==frame for source,frame in saved)
    assert model.low_tick==model.high_tick==0
    return c,model


@pytest.mark.parametrize('profile',PROFILES)
def test_unchanged_reference_derives_protection_release_weak_new_owner_and_old_fallback(profile):
    c,model=derive(Program(profile))
    assert [row['branch'] for row in c.admissions]==[c.program.old,c.program.new]
    assert all(row['counter'] in (3,4) for row in c.admissions)
    assert len(c.long_records)==4


@pytest.mark.parametrize('profile',PROFILES)
def test_taken_fallback_does_not_turn_the_earlier_not_taken_conditional_into_taken(profile):
    p=Program(profile);c=Checks(p,Coverage(p));c.pipeline=NS(current_event=None)
    for number,(branch,taken,path) in enumerate(((p.old,p.old_taken,p.original(p.old)),
            (p.new,p.new_taken,p.admission)),start=1):
        if number==2:
            c.ledgers[p.old].counter=7 if p.old_taken else 0
            c.ledgers[p.old].protection=0
        request=Feedback(path.branch_pc,path.match_context,path.read_indices,
            (Source(True,2,False,0,0,False,not taken),),2 if taken else 12,True,1 if taken else 3)
        c.learning_effect(request,NS(sequence=number),NS(candidate=0,wrong_position=2),number*10)
        assert request.taken is True
        assert c.active_owner==branch and c.states()[branch]==(4 if taken else 3,1)
    assert [row['branch'] for row in c.admissions]==[p.old,p.new]


@pytest.mark.parametrize('profile',PROFILES)
def test_competition_uses_common_real_predecessors_but_complete_distinct_tags(profile):
    p=Program(profile);a,b=p.paths
    assert a.pcs==b.pcs and a.read_indices==b.read_indices
    assert a.tags[0]!=b.tags[0] and a.branch_pc!=b.branch_pc
    assert p.admission.short_identity==p.original(p.new).short_identity
    assert all(p.helper(branch).read_indices[0]!=a.read_indices[0] for branch in ('left','right'))
    assert len({p.helper(branch).read_indices[0] for branch in ('left','right')})==2
    assert len({p.helper(branch).read_indices[1] for branch in ('left','right')})==2
    assert all(p.helper(branch).ahead_key==p.original(branch).ahead_key for branch in ('left','right'))
    assert not p.state()['physical_enumeration'] and not p.state()['new_predictor_algorithm']


@pytest.mark.parametrize('fault',('protected-old','old-not-strong','newcomer-first','wrong-complete-tag','wrong-result'))
def test_illegal_short_ownership_transfer_is_rejected_at_its_original_effect(fault):
    p=Program(PROFILES[0]);c=Checks(p,Coverage(p))
    c.pipeline=NS(current_event=None)
    c.active_owner=p.old;c.ledgers[p.old]=ProtectionLedger(counter=0,protection=0)
    path=p.admission
    request=Feedback(path.branch_pc,path.match_context,path.read_indices,
        (Source(True,2,False,0,0,False,p.old_taken),),2,p.new_taken,1)
    if fault=='protected-old':c.ledgers[p.old].protection=1
    elif fault=='old-not-strong':c.ledgers[p.old].counter=3
    elif fault=='newcomer-first':c.active_owner=None
    elif fault=='wrong-complete-tag':
        folds=list(request.context.folds);folds[TAG_FOLDS[0]]^=1
        request=replace(request,context=Context(tuple(folds)))
    else:request=replace(request,taken=p.old_taken)
    with pytest.raises(AssertionError):c.learning_effect(request,NS(sequence=2),NS(candidate=0,wrong_position=2),20)


def complete_checks(profile=PROFILES[0]):
    p=Program(profile);coverage=Coverage(p);c=Checks(p,coverage)
    c.pipeline=NS(current_event=NS(tick=200),raise_failure=lambda:None)
    c.active_owner=p.new
    c.ledgers={p.old:ProtectionLedger(counter=7 if p.old_taken else 0,protection=0),
        p.new:ProtectionLedger(counter=4 if p.new_taken else 3,protection=1)}
    c.admissions=[dict(branch=p.old,owner=1),dict(branch=p.new,owner=2,counter=4 if p.new_taken else 3)]
    c.storage_checks=[]
    weak=4 if p.new_taken else 3
    for phase in ('protected','released','new-owner'):
        owner=p.new if phase=='new-owner' else p.old
        c.storage_checks.append(dict(phase=phase,tick=100,owner=owner,
            protection={'protected':3,'released':0,'new-owner':1}[phase],
            entry=dict(tag=c.identities[owner].tag,counter=weak if owner==p.new else 7 if p.old_taken else 0)))
    phases=('new-long-while-old-protected','new-short-after-replacement','old-own-fallback',
        'new-original-long-preserved','old-original-long-preserved')
    c.queries=[dict(phase=phase,owner=10+i,query_tick=110+i,
        actual=None if phase=='old-own-fallback' else (0 if phase=='new-short-after-replacement' else 1,weak,p.new_taken))
        for i,phase in enumerate(phases)]
    original=NS(meta=NS(resolve=dict(value=1),redirect=dict(value=2)))
    c.originals=[(original,deepcopy(original.meta.resolve),deepcopy(original.meta.redirect))]
    for rule in RULES:c.mark(rule)
    return c,coverage


@pytest.mark.parametrize('profile',PROFILES)
def test_only_complete_lifetime_credits_its_own_direction_and_owner(profile):
    c,coverage=complete_checks(profile)
    c.finish_competition();assert coverage.groups['checked'].coverage==25
    with pytest.raises(AssertionError):c.finish_competition()


@pytest.mark.parametrize('missing',RULES)
def test_any_missing_human_obligation_prevents_checked_credit(missing):
    c,coverage=complete_checks();c.completed.remove(missing)
    with pytest.raises(AssertionError):c.finish_competition()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('pending-short','pending-long','wrong-active-owner','wrong-admission-order',
    'borrowed-strong-counter','missing-storage','missing-fallback','duplicate-consumer','stale-before-new-SRAM',
    'duplicate-source','replayed-short-effect','replayed-long-effect','missing-actual-long-write','wrong-SRAM-owner',
    'wrong-new-SRAM-counter','missing-own-fallback','wrong-short-provider','wrong-short-initial-counter','mutated-original'))
def test_incomplete_or_wrong_owner_evidence_does_not_publish_checked(fault):
    c,coverage=complete_checks()
    if fault=='pending-short':c.pending_protection=(c.program.new,1,200)
    elif fault=='pending-long':c.pending_long=[('unobserved',2,200)]
    elif fault=='wrong-active-owner':c.active_owner=c.program.old
    elif fault=='wrong-admission-order':c.admissions.reverse()
    elif fault=='borrowed-strong-counter':c.admissions[-1]['counter']=7
    elif fault=='missing-storage':c.storage_checks.pop()
    elif fault=='missing-fallback':c.queries.pop(2)
    elif fault=='duplicate-consumer':c.queries.append(deepcopy(c.queries[0]))
    elif fault=='stale-before-new-SRAM':c.queries[-1]['query_tick']=100
    elif fault=='duplicate-source':c.queries[-1]['owner']=c.queries[0]['owner']
    elif fault=='replayed-short-effect':c.learning.append(dict(owner=1))
    elif fault=='replayed-long-effect':c.long_events=[dict(owner=3),dict(owner=3)]
    elif fault=='missing-actual-long-write':c.long_events=[dict(owner=3)]
    elif fault=='wrong-SRAM-owner':c.storage_checks[0]['owner']=c.program.new
    elif fault=='wrong-new-SRAM-counter':c.storage_checks[-1]['entry']['counter']=7
    elif fault=='missing-own-fallback':c.queries[2]['actual']=(0,7,True)
    elif fault=='wrong-short-provider':c.queries[1]['actual']=(1,4,True)
    elif fault=='wrong-short-initial-counter':c.queries[1]['actual']=(0,7,True)
    else:c.originals[0][0].meta.resolve['value']=99
    with pytest.raises(AssertionError):c.finish_competition()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('field',('valid','tag','position','counter'))
def test_actual_shared_SRAM_cannot_be_substituted_by_a_cached_or_wrong_owner(field):
    c,_=complete_checks();c.storage_layout=(8,4,3,1)
    identity=c.identities[c.program.new];counter=c.ledgers[c.program.new].counter
    word=(((((1<<8)|identity.tag)<<4|2)<<3|counter)<<1)
    word^={'valid':1<<16,'tag':1<<8,'position':1<<4,'counter':1<<1}[field]
    c.native_storage=dict(words=(word,),cells=())
    with pytest.raises(AssertionError):c.check_storage('new-owner')


@pytest.mark.parametrize('profile',(None,'bank0','left.old-weak','third.old-T'))
def test_unknown_or_coordinate_only_competition_programs_are_rejected(profile):
    with pytest.raises(ValueError):Program(profile)


@pytest.mark.parametrize('fault',(None,'valid','data_valid','index','tag','position','counter','useful','wrong-boundary'))
def test_every_long_allocation_or_update_needs_the_actual_complete_retained_write(monkeypatch,fault):
    from suites.frontend.bpu.bpu.checker.short_context_ownership import ShortContextChecks
    monkeypatch.setattr(ShortContextChecks,'candidates',lambda *args:())
    p=Program(PROFILES[0]);c=Checks(p,Coverage(p));path=p.original(p.new)
    key=(p.new,path.read_indices[1],path.tags[1])
    c.pipeline=NS(current_event=NS(tick=102))
    c.long_records[key]=ProtectionLedger(counter=4,protection=2)
    c.pending_long=[(key,2,100)]
    cells=[dict(valid=0,data_valid=0,index=0,tag=0,position=0,counter=0) for _ in range(8)]
    cells[0]=dict(valid=1,data_valid=1,index=key[1],tag=key[2],position=2,counter=4)
    useful=[[0]*512,[0]*512];useful[1][key[1]]=2
    if fault in cells[0]:cells[0][fault]^=1
    elif fault=='useful':useful[1][key[1]]=1
    elif fault=='wrong-boundary':c.pipeline.current_event.tick=100
    row=dict(observed=dict(short_storage=dict(),early_direction=dict(useful=useful),competition_long=dict(cells=cells,enq=1)))
    if fault is None:
        c.candidates(row);assert len(c.actual_long_writes)==1 and not c.pending_long
    else:
        with pytest.raises(AssertionError):c.candidates(row)
        assert not c.actual_long_writes
