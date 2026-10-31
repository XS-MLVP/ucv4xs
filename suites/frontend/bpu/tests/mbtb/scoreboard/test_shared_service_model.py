"""Capacity-safe concurrent obligations, independent of generated signal code."""
from dataclasses import replace
import pytest
from suites.frontend.bpu.mbtb.model.semantic import RetainedEntries,Write,Entry,Target


@pytest.mark.parametrize('reverse',(False,True))
@pytest.mark.parametrize('busy',(False,True))
@pytest.mark.parametrize('pending',(False,True))
@pytest.mark.parametrize('owner',(0,1))
def test_distinct_clear_and_retained_correction_both_survive_when_capacity_exists(reverse,busy,pending,owner):
    cache=RetainedEntries();old=Write(3,owner,Entry(7,5,3,0,Target(0x100)))
    cache.advance(True,(old,))
    if not pending:assert cache.advance(False)==(old,)
    changed=replace(old,way=1-owner,entry=replace(old.entry,target=Target(0x200)))
    clear=Write(1,owner,None)
    incoming=(clear,changed) if reverse else (changed,clear)
    old_version=next(iter(cache.records.values()))
    retired=cache.advance(busy,incoming)
    assert old_version.write==old
    latest=replace(changed,way=owner)
    assert cache.owner(changed)==owner
    assert {v.write for v in cache.records.values()}=={latest,clear}
    assert len({v.rank for v in cache.records.values()})==2
    services=cache.advance(False)+cache.advance(False)
    assert set(services)=={latest,clear} and len(services)==2
    assert retired==((old,) if pending and not busy else ())
    assert cache.overflows==0 and not cache.outstanding


@pytest.mark.parametrize('owner',(0,1))
@pytest.mark.parametrize('reverse',(False,True))
def test_two_distinct_new_obligations_do_not_reuse_the_same_free_capacity(owner,reverse):
    c=RetainedEntries();a=Write(1,owner,Entry(2,1,3,0,Target(0x100)));b=Write(3,owner,None)
    c.advance(True,(b,a) if reverse else (a,b))
    assert set(c.advance(False)+c.advance(False))=={a,b}
    assert c.overflows==0
