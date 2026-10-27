"""Invalidations have destination identity, independent of payload bits."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import ScoreboardMismatch
from bpuverify.mbtb.model.semantic import RetainedEntries,Write,Entry,Target,coordinate,tag
from bpuverify.bpu.model.main_service import entry_payload
from bpuverify.bpu.model.main_duplicate_cleanup import Program,IDENTITIES,OVERLAPS,PREPARATIONS,RULES
from bpuverify.bpu.coverage.main_duplicate_cleanup import Coverage
from bpuverify.bpu.checker.main_duplicate_cleanup import Checks
from tests.bpu.scoreboard.test_partial_reuse import transfer
from bpuverify.bpu.model.selection import Branch,Kind,early,middle,final

PROGRAMS=tuple(Program(i,o,p) for i in IDENTITIES for o in OVERLAPS for p in PREPARATIONS)


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_reference_clear_never_borrows_valid_zero_branch_identity_or_neighbor_destination(p):
    cache=RetainedEntries();row=coordinate(p.pc)[2];other=coordinate(p.neighbor)[2]
    a=Write(row,2,Entry(tag(p.pc),p.position,3,0,Target.encode(p.pc,p.target)))
    old=Write(other,2,Entry(tag(p.neighbor),3,3,0,Target.encode(p.query_neighbor,p.neighbor_target)))
    cache.advance(True,(a,));cache.advance(True,(old,));cache.advance(False);cache.advance(False)
    clear=Write(row,3,None)
    update=Write(other,2,Entry(tag(p.neighbor),3,3,0,Target.encode(p.query_neighbor,p.updated_neighbor_target)))
    offers=(update,clear) if p.concurrent else (clear,)
    assert cache.key(clear)!=cache.key(a) and cache.owner(clear)==3
    cache.advance(True,offers)
    assert cache.records[cache.key(a)].write==a
    actual=cache.advance(False)
    by_owner=tuple(tuple(entry_payload(w.row,Entry() if w.entry is None else w.entry)
        for w in actual if w.way==owner) for owner in range(4))
    assert by_owner==p.expected_services and not cache.outstanding


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_program_uses_logical_identity_and_independent_destinations_not_a_bank_grid(p):
    assert coordinate(p.pc)==(0,0,1) and coordinate(p.neighbor)==(0,0,3)
    assert (tag(p.pc)==p.position==0)==(p.identity=='zero-tag-and-position')
    assert p.cleared['kind']==0 and p.cleared['tag']==p.cleared['position']==0
    assert p.neighbor_effect['row']!=p.cleared['row']
    assert not p.state()['physical_coordinate_enumeration']


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_exact_destination_services_and_original_qualified_input_shape(p):
    env=NS(checker=NS(current_event=None,raise_failure=lambda:None))
    checks=Checks(env,p)
    checks.last=(10,dict(read={},writes=[],dirty=[],queue={}))
    for owner,expected in enumerate(p.expected_services):
        for payload in expected:checks.write_accepted(owner,transfer(11,deepcopy(payload)))
    if p.concurrent:checks.write_accepted(4,transfer(11,dict(row=coordinate(p.neighbor)[2],mask=4,counters=[0,0,2,0])))
    assert checks.complete() and checks.board.status.failed==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('damage',('clear-wrong-destination','wrong-clear-row','clear-still-valid','wrong-target','extra-clear','unexpected-direction'))
def test_wrong_service_cannot_be_hidden_by_matching_zero_payload_or_final_counts(p,damage):
    checks=Checks(NS(checker=NS(current_event=None,raise_failure=lambda:None)),p)
    checks.last=(10,dict(read={},writes=[],dirty=[],queue={}))
    value=deepcopy(p.cleared);owner=3
    with pytest.raises(ScoreboardMismatch) as first:
        if damage=='clear-wrong-destination':owner=2
        elif damage=='wrong-clear-row':value['row']^=1
        elif damage=='clear-still-valid':value['kind']=3
        elif damage=='wrong-target':value['offset']=1
        elif damage=='extra-clear':checks.write_accepted(owner,transfer(11,deepcopy(value)))
        else:
            # A basic clear has no direction, and an overlap has exactly one.
            bits=dict(row=coordinate(p.neighbor)[2],mask=4,counters=[0,0,2,0])
            if p.concurrent:checks.write_accepted(4,transfer(11,bits))
            checks.write_accepted(4,transfer(13,bits))
        checks.write_accepted(owner,transfer(15,value))
    before=deepcopy(checks.summary())
    with pytest.raises(ScoreboardMismatch) as second:checks.complete()
    assert first.value is second.value and checks.summary()==before


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_no_checked_credit_without_every_qualification_clear_service_and_consumer(p,missing):
    c=Coverage(p)
    for rule in RULES:
        if rule!=missing:c.reach(rule)
    with pytest.raises(AssertionError):c.finish()
    assert c.groups['checked'].coverage==0


@pytest.mark.parametrize('p',PROGRAMS,ids=lambda p:p.label)
def test_complete_program_credits_only_its_own_nine_obligations(p):
    c=Coverage(p)
    for rule in RULES:c.reach(rule)
    c.finish();assert c.groups['checked'].coverage==12.5
    with pytest.raises(AssertionError):c.finish()


@pytest.mark.parametrize('identity,overlap',(('bank1','cleanup-only'),('nonzero-identity','slot1'),(True,'cleanup-and-learning'),('zero-tag-and-position',False)))
def test_physical_coordinates_are_not_additional_semantic_profiles(identity,overlap):
    with pytest.raises(ValueError):Program(identity,overlap)


@pytest.mark.parametrize('stage',('early','middle','final'))
@pytest.mark.parametrize('position',(0,5,15))
def test_equal_position_tie_is_larger_candidate_for_every_nonempty_valid_mask(stage,position):
    # Exhaustive semantic candidate masks, no DUT/physical coordinate sweep.
    for mask in range(1,16):
        entries=tuple(Branch(position,0x40010000+index*16,Kind.DIRECT) if mask&(1<<index) else None for index in range(4))
        if stage=='early':choice=early(0x40000000,ahead=entries,short_history=(None,)*4)
        elif stage=='middle':choice=middle(0x40000000,entries,(None,)*4)
        else:choice=final(0x40000000,entries,(None,)*4,(None,)*4)
        assert choice.owner==mask.bit_length()-1
        assert choice.branch.target==entries[choice.owner].target


@pytest.mark.parametrize('stage',('early','middle','final'))
def test_position_order_still_precedes_tie_index_and_disabled_peer_never_wins(stage):
    entries=(Branch(3,0x40001000,Kind.CONDITIONAL),Branch(1,0x40002000,Kind.DIRECT),
        Branch(3,0x40003000,Kind.DIRECT),Branch(1,0x40004000,Kind.CONDITIONAL,False))
    if stage=='early':choice=early(0x40000000,ahead=entries,short_history=(None,)*4)
    elif stage=='middle':choice=middle(0x40000000,entries,(None,)*4)
    else:choice=final(0x40000000,entries,(None,)*4,(None,)*4)
    assert choice.owner==1 and choice.branch.target==0x40002000
