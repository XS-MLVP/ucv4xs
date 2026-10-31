"""Semantic schedule discriminators; no DUT, signals or coverage credit."""
from dataclasses import replace
from copy import deepcopy
import ast
from pathlib import Path
import pytest

from suites.frontend.bpu.bpu.model.window_lifetime import WindowLifetimes,LifetimeError,freeze

META={'history':[0,1],'owner':{'counter':0,'hit':False}}
PAYLOAD={'branches':[{'position':1,'target':0x40000800,'taken':True}]}


def qualify(model,source):return model.qualify(model.resolve(source,PAYLOAD))
def accept(model,teaching):return model.accept(teaching,metadata=META,payload=PAYLOAD)


def test_model_has_no_hardware_framework_or_predictor_algorithm_import():
    tree=ast.parse((Path(__file__).resolve().parents[3] / 'bpu/model/window_lifetime.py').read_text())
    assert not any(isinstance(n,ast.Import) for n in ast.walk(tree))
    assert {n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}=={'dataclasses','collections.abc'}


def test_younger_resolve_then_older_resolve_is_legal_while_both_originals_survive():
    m=WindowLifetimes(8)
    old=m.admit(0x40000800,metadata=META)
    young=m.admit(0x40000800,metadata=META)
    assert old is not young and old.sequence<young.sequence
    first=qualify(m,young);accept(m,first)
    second=qualify(m,old);accept(m,second)
    assert [t.source for t in m.accepted]==[young,old]
    with pytest.raises(LifetimeError,match='commit cannot pass'):m.commit(young)
    m.commit(old);m.commit(young)
    assert not m.active


def test_same_PC_same_metadata_and_equal_clone_do_not_replace_an_original_occurrence():
    m=WindowLifetimes(2)
    original=m.admit(1,metadata=META)
    other=m.admit(1,metadata=META)
    fake=replace(original)
    for value in (fake,replace(original,sequence=other.sequence)):
        with pytest.raises(LifetimeError,match='impersonated'):m.resolve(value,PAYLOAD)
    assert m.metadata[original.sequence]==m.metadata[other.sequence]
    assert original is not other


@pytest.mark.parametrize('capacity',(1,2,8))
def test_full_window_set_backpressures_without_overwriting_or_mutating_state(capacity):
    m=WindowLifetimes(capacity)
    sources=[m.admit(100+i,metadata=META) for i in range(capacity)]
    assert not m.accepting
    before=m.state()
    with pytest.raises(LifetimeError,match='full window'):m.admit(100,metadata=META)
    assert m.state()==before
    m.commit(sources[0])
    new=m.admit(100,metadata=META)
    assert new.slot==sources[0].slot and new is not sources[0]


@pytest.mark.parametrize('prepared',(False,True))
def test_redirect_discards_younger_lifetime_but_preserves_owner_and_older_prefix(prepared):
    m=WindowLifetimes(4)
    older,owner,younger=[m.admit(i,metadata=META) for i in range(3)]
    pending=qualify(m,younger) if prepared else None
    assert m.redirect(owner)==(younger,)
    assert m.active==[older,owner]
    late=m.resolve(younger,PAYLOAD)
    with pytest.raises(LifetimeError,match='flushed'):m.qualify(late)
    if prepared:
        with pytest.raises(LifetimeError,match='no exact pending'):accept(m,pending)
    accept(m,qualify(m,older))
    accept(m,qualify(m,owner))
    successor=m.admit(10,metadata=META)
    assert successor.slot==younger.slot and successor is not younger


def test_redirect_from_young_window_does_not_discard_an_older_unresolved_source():
    m=WindowLifetimes(8)
    old=m.admit(1,metadata=META)
    young=m.admit(2,metadata=META)
    m.admit(3,metadata=META)
    m.redirect(young)
    accept(m,qualify(m,old))
    assert m.accepted[0].source is old


@pytest.mark.parametrize('prepared',(False,True))
def test_metadata_reuse_before_qualification_is_not_the_same_as_after_original_snapshot(prepared):
    m=WindowLifetimes(1)
    old=m.admit(1,metadata=META)
    original=m.resolve(old,PAYLOAD)
    teaching=m.qualify(original) if prepared else None
    m.commit(old)
    fresh=m.admit(1,metadata={'new':'different original'})
    assert fresh.slot==old.slot
    if prepared:
        accept(m,teaching)
        assert m.accepted[0].source is old and m.accepted[0].metadata==freeze(META)
    else:
        with pytest.raises(LifetimeError):m.qualify(original)
    assert m.slots[fresh.slot] is fresh


@pytest.mark.parametrize('stage',('before-metadata','after-metadata','prepared'))
def test_reset_ends_all_previous_source_and_teaching_epochs(stage):
    m=WindowLifetimes(2)
    old=m.admit(1)
    if stage!='before-metadata':m.publish_metadata(old,META)
    original=m.resolve(old,PAYLOAD)
    teaching=m.qualify(original) if stage=='prepared' else None
    m.reset()
    fresh=m.admit(1,metadata=META)
    assert fresh.epoch!=old.epoch
    with pytest.raises(LifetimeError):m.qualify(original)
    with pytest.raises(LifetimeError,match='old reset'):m.resolve(old,PAYLOAD)
    if teaching is not None:
        with pytest.raises(LifetimeError):accept(m,teaching)
    accept(m,qualify(m,fresh))


def test_metadata_publication_is_required_and_cannot_be_republished_from_new_wire_values():
    m=WindowLifetimes(2)
    source=m.admit(10)
    original=m.resolve(source,PAYLOAD)
    before=m.state()
    with pytest.raises(LifetimeError,match='not yet published'):m.qualify(original)
    assert m.state()==before
    value=deepcopy(META)
    m.publish_metadata(source,value)
    value['owner']['counter']=7
    teaching=m.qualify(original)
    assert teaching.metadata==freeze(META)
    with pytest.raises(LifetimeError,match='already published'):m.publish_metadata(source,value)
    accept(m,teaching)


def test_single_cached_teaching_cannot_be_overwritten_by_another_eligible_resolve():
    m=WindowLifetimes(2)
    a,b=[m.admit(i,metadata=META) for i in range(2)]
    first=qualify(m,a)
    other=m.resolve(b,PAYLOAD)
    before=m.state()
    with pytest.raises(LifetimeError,match='still awaits'):m.qualify(other)
    assert m.state()==before and m.cached is first
    accept(m,first)
    accept(m,m.qualify(other))


def test_commit_releases_capacity_but_does_not_immediately_destroy_original_metadata_eligibility():
    m=WindowLifetimes(2)
    original=m.admit(1,metadata=META)
    queued=m.resolve(original,PAYLOAD)
    m.commit(original)
    assert not m.active and m.slots[original.slot] is original
    teaching=m.qualify(queued)
    accept(m,teaching)
    assert m.accepted[0].source is original


def test_commit_is_not_inferred_from_successful_predictor_training():
    m=WindowLifetimes(1)
    original=m.admit(1,metadata=META)
    accept(m,qualify(m,original))
    assert m.active==[original] and not m.accepting
    with pytest.raises(LifetimeError,match='full window'):m.admit(2,metadata=META)


def test_multiple_distinct_resolve_arrivals_can_reference_one_original_without_rebinding_metadata():
    m=WindowLifetimes(2)
    original=m.admit(1,metadata=META)
    first=m.qualify(m.resolve(original,{'position':1}))
    m.accept(first,metadata=META,payload={'position':1})
    second=m.qualify(m.resolve(original,{'position':5}))
    m.accept(second,metadata=META,payload={'position':5})
    assert len(m.accepted)==2 and all(t.source is original for t in m.accepted)


@pytest.mark.parametrize('kind',('resolve','teaching'))
def test_equal_but_forged_resolve_or_cached_teaching_cannot_steal_an_original_occurrence(kind):
    m=WindowLifetimes(1)
    source=m.admit(1,metadata=META)
    resolution=m.resolve(source,PAYLOAD)
    if kind=='resolve':
        with pytest.raises(LifetimeError,match='exact original resolve'):m.qualify(replace(resolution))
    else:
        teaching=m.qualify(resolution)
        with pytest.raises(LifetimeError,match='exact pending'):accept(m,replace(teaching))


def test_correction_rewinds_tail_but_never_reuses_an_older_surviving_window():
    m=WindowLifetimes(3)
    older,owner,wrong=[m.admit(i,metadata=META) for i in range(3)]
    m.redirect(owner)
    replacement=m.admit(2,metadata=META)
    assert replacement.slot==wrong.slot
    assert m.active==[older,owner,replacement] and not m.accepting
    accept(m,qualify(m,older))
    with pytest.raises(LifetimeError):m.qualify(m.resolve(wrong,PAYLOAD))


@pytest.mark.parametrize('field',('metadata','payload'))
def test_actual_acceptance_must_preserve_the_complete_original_snapshot(field):
    m=WindowLifetimes(2)
    original=m.admit(1,metadata=META)
    teaching=qualify(m,original)
    values=dict(metadata=deepcopy(META),payload=deepcopy(PAYLOAD))
    if field=='metadata':values['metadata']['history'][1]=9
    else:values['payload']['branches'][0]['target']+=2
    before=m.state()
    with pytest.raises(LifetimeError,match='changed') as error:m.accept(teaching,**values)
    assert error.value.expected!=error.value.actual and error.value.source is original
    assert m.state()==before
    accept(m,teaching)


def test_resolve_and_teaching_cannot_be_qualified_or_accepted_twice():
    m=WindowLifetimes(1)
    source=m.admit(1,metadata=META)
    resolution=m.resolve(source,PAYLOAD)
    teaching=m.qualify(resolution)
    accept(m,teaching)
    with pytest.raises(LifetimeError,match='already qualified'):m.qualify(resolution)
    with pytest.raises(LifetimeError,match='no exact pending'):accept(m,teaching)


@pytest.mark.parametrize('bad',(0,-1,True,None,1.5))
def test_capacity_is_an_explicit_positive_semantic_parameter(bad):
    with pytest.raises(ValueError):WindowLifetimes(bad)


@pytest.mark.parametrize('bad',(-1,True,None,1.5))
def test_bad_source_admission_does_not_mutate_state(bad):
    m=WindowLifetimes(2);before=m.state()
    with pytest.raises(ValueError):m.admit(bad,metadata=META)
    assert m.state()==before


@pytest.mark.parametrize('bad',({1:'not a named field'},object(),{'native':object()}))
def test_native_handles_or_ambiguous_metadata_shapes_are_not_golden_input_snapshots(bad):
    m=WindowLifetimes(2);before=m.state()
    with pytest.raises(TypeError):m.admit(1,metadata=bad)
    assert m.state()==before
