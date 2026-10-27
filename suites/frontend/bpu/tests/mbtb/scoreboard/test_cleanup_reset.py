"""Independent legal-source replay, reset lifetime and rejection controls."""
from copy import deepcopy
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch

from bpuverify.mbtb.model.semantic import Branch as Outcome,Events,Feedback,MbtbReference,Source,tag,coordinate
from bpuverify.mbtb.transaction.types import MbtbEntry,MbtbPrediction
from bpuverify.mbtb.model.cleanup_reset import Program,PROFILES,RULES
from bpuverify.mbtb.coverage.cleanup_reset import Coverage
from bpuverify.mbtb.checker.cleanup_reset import Checks



def query(model,pc):
    for _ in range(2):model.advance(Events(pc=pc,select=True,advance=True))
    assert model.frame.pc==pc
    return model.frame


def feedback(frame,branch,*,taken=True,allocate=True):
    sources=tuple(tuple(Source(entry.valid and entry.tag==tag(read.pc),read.ordinal*16+entry.position,
        entry.kind,entry.action,counter) for entry,counter in zip(read.entries,read.counters,strict=True))+(Source(),)
        for read in frame.banks)
    return Feedback((frame.pc,(frame.pc//16+1)*16),sources,(
        Outcome(branch.target,taken,branch.position,branch.kind,mispredict=allocate),))


def idle(model):
    for _ in range(16):
        model.advance()
        if (model.offered is None and not any(model.entry_offers.values())
                and not any(cache.outstanding for cache in model.entries.values())
                and not any(queue.pending for queue in model.directions.values()) and not model.cleanup and not model.snapshots):return
    raise AssertionError('independent branch obligations did not drain')


def learn(model,source,branch,**kwargs):
    model.advance(Events(feedback=feedback(source,branch,**kwargs)))
    idle(model)


def duplicates(program):
    model=MbtbReference()
    old=query(model,program.old.pc)
    neighbor=query(model,program.neighbor.pc)
    learn(model,old,program.old)
    for ordinal in range(1,4):
        branch=replace(program.neighbor,pc=program.neighbor.pc+128*ordinal,target=program.neighbor.target+0x200*ordinal)
        learn(model,query(model,branch.pc),branch)
    learn(model,neighbor,program.neighbor)
    learn(model,old,program.changed)
    frame=query(model,program.old.pc)
    return model,frame


@pytest.mark.parametrize('profile',PROFILES)
def test_legal_old_sources_derive_both_cleanup_reset_phases_without_state_seeding(profile):
    program=Program(profile)
    model,frame=duplicates(program)
    values=frame.values()
    assert sorted(values[f'{slot}.target'] for slot in range(10) if values[f'{slot}.valid'])==sorted((program.old.target,program.changed.target))
    assert not model.cleanup and not any(model.entry_offers.values())
    frozen=deepcopy(frame)
    if profile=='registered-invalidation':
        model.advance(Events(consume=True))
        clear=[write for writes in model.entry_offers.values() for write in writes]
        assert len(clear)==1 and clear[0].entry is None and clear[0].way==3
    model.advance(Events(reset=True))
    assert not model.memory and not model.counters and model.read is model.frame is model.offered is None
    assert not model.cleanup and not any(model.entry_offers.values())
    assert all(not cache.records and not cache.outstanding for cache in model.entries.values())
    for branch in (program.new,program.new_neighbor):
        cold=query(model,branch.pc)
        assert not any(cold.values()[f'{slot}.raw_hit'] for slot in range(10))
        learn(model,cold,branch)
    new=query(model,program.new.pc)
    active=next(slot for slot in range(10) if new.values()[f'{slot}.valid'])
    assert (new.values()[f'{active}.target'],new.values()[f'{active}.kind'],new.values()[f'{active}.counter'])==(
        program.new.target,program.new.kind,2)
    learn(model,new,program.new,taken=False,allocate=False)
    fresh=query(model,program.new.pc).values()
    assert fresh[f'{active}.valid'] and fresh[f'{active}.counter']==1 and not fresh[f'{active}.taken']
    assert frame==frozen


def registered():
    program=Program('registered-invalidation')
    align,bank,row=coordinate(program.old.pc)
    receipt=dict(tick=9,align=align,bank=bank,row=row,way=3,tag=tag(program.old.pc),position=program.old.position)
    clear=dict(align=align,bank=bank,row=row,way=3,tag=0,position=0,kind=0,action=0,carry=0,lower=0)
    return program,[receipt],dict(tick=10,clears=[clear],consumed_reset=False)


def test_actual_consumption_and_registered_clear_are_both_required_for_positive_stage():
    program,receipts,native=registered()
    Checks(program).stage(receipts,native)
    Checks(Program('observed-not-consumed')).stage([],dict(native,clears=[]))


@pytest.mark.parametrize('fault',('no-consumption','no-request','wrong-original-tag','wrong-original-position',
    'wrong-original-row','wrong-destination','not-invalidation','target-payload','future-consumption'))
def test_wrong_or_fabricated_cleanup_stage_is_rejected(fault):
    program,receipts,native=registered()
    if fault=='no-consumption':receipts=[]
    elif fault=='no-request':native['clears']=[]
    elif fault=='wrong-original-tag':receipts[0]['tag']+=1
    elif fault=='wrong-original-position':receipts[0]['position']+=1
    elif fault=='wrong-original-row':receipts[0]['row']+=1
    elif fault=='wrong-destination':native['clears'][0]['way']=0
    elif fault=='not-invalidation':native['clears'][0]['kind']=1
    elif fault=='target-payload':native['clears'][0]['lower']=0x456
    else:receipts[0]['tick']=native['tick']+2
    with pytest.raises(ScoreboardMismatch) as error:Checks(program).stage(receipts,native)
    assert error.value.context.request['program']==program.state()


@pytest.mark.parametrize('fault',('consumption','registered-request'))
def test_cached_only_control_cannot_hide_an_already_accepted_cleanup(fault):
    _,receipts,native=registered()
    if fault=='consumption':native['clears']=[]
    else:receipts=[]
    with pytest.raises(ScoreboardMismatch):Checks(Program('observed-not-consumed')).stage(receipts,native)


def prediction(branch,*,counter):
    entries=[MbtbEntry(0,0,0,0,0,0) for _ in range(10)]
    entries[1]=MbtbEntry(1,int(counter>=2),branch.target,branch.position,branch.kind,0)
    meta=[[dict(rawHit=0,position=0,attribute=dict(branchType=0,rasAction=0),counter_value=0) for _ in range(2)] for _ in range(2)]
    meta[0][1]=dict(rawHit=1,position=branch.position,attribute=dict(branchType=branch.kind,rasAction=0),counter_value=counter)
    return MbtbPrediction(tuple(entries),meta)


@pytest.mark.parametrize('fault',('missing','old-target','old-kind','position','action','wrong-direction','counter','raw-owner'))
def test_new_epoch_consumer_cannot_accept_old_or_corrupted_instruction(fault):
    program=Program(PROFILES[0])
    value=prediction(program.new,counter=1)
    fields=dict(missing='valid',position='position',action='ras_action')
    if fault in fields:value=replace(value,entries=(value.entries[0],replace(value.entries[1],**{fields[fault]:getattr(value.entries[1],fields[fault])^1}),*value.entries[2:]))
    elif fault=='old-target':value=replace(value,entries=(value.entries[0],replace(value.entries[1],target=program.old.target),*value.entries[2:]))
    elif fault=='old-kind':value=replace(value,entries=(value.entries[0],replace(value.entries[1],branch_type=program.old.kind),*value.entries[2:]))
    elif fault=='wrong-direction':value=replace(value,entries=(value.entries[0],replace(value.entries[1],taken=1),*value.entries[2:]))
    elif fault=='counter':value.meta_entries[0][1]['counter_value']=0
    else:value.meta_entries[0][1]['rawHit']=0
    with pytest.raises(ScoreboardMismatch):Checks(program).resident(value,program.new,counter=1)


@pytest.mark.parametrize('fault',('one-survivor','identical-targets','wrong-position','wrong-raw-source'))
def test_duplicate_precondition_requires_two_distinct_complete_original_records(fault):
    program=Program(PROFILES[0])
    first=prediction(program.old,counter=2)
    second=prediction(program.changed,counter=2)
    entries=list(first.entries)
    entries[0]=second.entries[1]
    first.meta_entries[0][0]=deepcopy(first.meta_entries[0][1])
    if fault=='one-survivor':entries[0]=replace(entries[0],valid=0)
    elif fault=='identical-targets':entries[0]=replace(entries[0],target=program.old.target)
    elif fault=='wrong-position':entries[0]=replace(entries[0],position=3)
    else:first.meta_entries[0][0]['position']=3
    with pytest.raises(ScoreboardMismatch):Checks(program).duplicate(replace(first,entries=tuple(entries)))


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',RULES)
def test_partial_cleanup_reset_lifetime_cannot_receive_checked_credit(profile,missing):
    coverage=Coverage(Program(profile))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_complete_lifetime_only_credits_its_own_profile_once(profile):
    coverage=Coverage(Program(profile))
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==50
    with pytest.raises(AssertionError):coverage.finish()
    with pytest.raises(ValueError):coverage.reach(RULES[0])


@pytest.mark.parametrize('profile',(None,'fresh-instance',True))
def test_weaker_or_unknown_reset_program_is_rejected(profile):
    with pytest.raises(ValueError):Program(profile)
