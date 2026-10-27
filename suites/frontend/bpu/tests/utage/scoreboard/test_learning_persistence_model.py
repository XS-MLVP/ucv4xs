"""Independent ledger controls and algorithm-only feasibility, before DUT credit."""
from copy import deepcopy
from dataclasses import replace
import pytest

from bpuverify.utage.model.semantic import Base, Context, Events, UtageReference
from bpuverify.utage.case.definitions import SHADOW_CAPACITY
from tests.utage.scoreboard.test_semantic_model import feedback, learn
from bpuverify.utage.model.learning_persistence import Program, PROFILES, MODES, PC, RULES
from bpuverify.utage.model.persistence import PersistenceLedger, Version
from bpuverify.utage.coverage.learning_persistence import Coverage



@pytest.mark.parametrize('profile,count', tuple(zip(PROFILES, (SHADOW_CAPACITY, SHADOW_CAPACITY+1, 2*SHADOW_CAPACITY+1))))
def test_program_exercises_logical_retention_boundary_without_physical_enumeration(profile, count):
    p = Program(profile, 'adjacent')
    assert p.count == count and len(set(p.histories)) == count
    for table in (0, 1):
        assert len({p.identity(h, table)[1] for h in p.histories}) == count
        assert all(p.identity(h, table)[2] < 256 for h in p.histories)
    assert p.state()['physical_enumeration'] is False


def version(owner=10, counter=4):
    return Version(owner, (1, 19, 54, 6), counter, 'learning')


def admitted(v=None):
    ledger = PersistenceLedger(); v = version() if v is None else v
    ledger.source(v, dict(owner=v.owner)); ledger.accept(dict(owner=v.owner), v.owner+2)
    return ledger, v


def test_acceptance_is_not_a_version_write_and_version_write_is_not_persistence():
    ledger, v = admitted()
    with pytest.raises(AssertionError, match='actual version write'):
        ledger.finish_phase([v.owner], persistent=False)
    ledger.publish(*v.identity[:2], v.entry, v.owner+4)
    ledger.finish_phase([v.owner], persistent=False)
    with pytest.raises(AssertionError, match='not actually persistent'):
        ledger.finish_phase([v.owner], persistent=True)
    ledger.service(*v.identity[:2], v.entry, v.owner+6)
    ledger.finish_phase([v.owner], persistent=True)


@pytest.mark.parametrize('fault', ('other-owner', 'mutated-payload', 'duplicate', 'too-early'))
def test_original_feedback_cannot_be_borrowed_replayed_or_mutated(fault):
    ledger = PersistenceLedger(); v = version(); payload=dict(owner=v.owner)
    ledger.source(v, payload)
    if fault == 'mutated-payload': payload['owner'] += 1
    if fault == 'other-owner': payload = dict(owner=999)
    if fault == 'duplicate': ledger.accept(payload, 12)
    with pytest.raises(AssertionError): ledger.accept(payload, 10 if fault == 'too-early' else 14)


@pytest.mark.parametrize('fault', ('table', 'index', 'tag', 'position', 'counter', 'before-input'))
def test_actual_version_must_match_the_complete_original_obligation(fault):
    ledger, v = admitted(); table,index=v.identity[:2];entry=v.entry
    if fault=='table':table=0
    elif fault=='index':index^=256
    elif fault in entry:entry[fault]^=1
    with pytest.raises(AssertionError):ledger.publish(table,index,entry,10 if fault=='before-input' else 14)


def test_a_newer_service_cannot_be_rolled_back_to_an_older_logical_version():
    ledger, old = admitted(); ledger.publish(*old.identity[:2], old.entry, 14)
    new=version(owner=20,counter=5);ledger.source(new,dict(owner=20));ledger.accept(dict(owner=20),22)
    ledger.publish(*new.identity[:2],new.entry,24);ledger.service(*new.identity[:2],new.entry,26)
    with pytest.raises(AssertionError,match='roll back'):ledger.service(*old.identity[:2],old.entry,28)


@pytest.mark.parametrize('fault',('unpublished','other-identity','invented-counter'))
def test_service_must_have_an_actual_prior_version(fault):
    ledger,v=admitted();table,index=v.identity[:2];entry=v.entry
    if fault!='unpublished':ledger.publish(table,index,entry,14)
    if fault=='other-identity':index^=256
    if fault=='invented-counter':entry['counter']=7
    with pytest.raises(AssertionError,match='invent'):ledger.service(table,index,entry,16)


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',RULES)
def test_missing_any_lifetime_obligation_blocks_checked_credit(profile,missing):
    c=Coverage(Program(profile,'serial'))
    for rule in RULES:
        if rule!=missing:c.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):c.finish()
    assert c.groups['checked'].samples==0


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('mode',MODES)
def test_independent_core_derives_long_allocation_rewards_and_persistence(profile,mode):
    p=Program(profile,mode);m=UtageReference();originals=[]
    for phase,position,table,expected_before in (('short',5,0,None),('allocate',6,1,None),
        ('reward',6,1,4),('reward-again',6,1,5)):
        sources=[]
        def predict(history):
            context=Context.from_recent(history)
            event=Events(read_pc=PC,read_context=context,select=True,pc=PC,context=context,
                positions=tuple(position+i for i in range(4)),
                bases=(Base(True,position,False,1),Base(),Base(),Base()),advance=True)
            m.advance(event);m.advance(event)
            return m.prediction
        for h in p.order(phase):
            source=predict(h)
            assert source.frame.providers()[0] == (None if expected_before is None else table)
            if expected_before is not None:assert source.frame.read.entries[table].counter==expected_before
            request=replace(feedback(source,taken=True),position=position)
            sources.append(request);originals.append((source,deepcopy(source)))
        for request in sources:
            if mode=='serial':learn(m,request)
            else:m.advance(Events(feedback=request))
        while m.offered is not None or m.learning is not None:m.advance()
        for _ in range(2):
            for h in p.histories:
                source=predict(h)
                assert source.frame.providers()[0]==table
                assert source.frame.read.entries[table].counter==p.counter(phase)
        assert all(m.memory[table][p.identity(h,table)[1]].counter==p.counter(phase) for h in p.histories)
    assert all(source==old for source,old in originals)
