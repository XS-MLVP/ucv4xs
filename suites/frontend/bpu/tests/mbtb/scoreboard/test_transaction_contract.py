"""Strict raw-halfword domains, sparse lanes and immutable complete metadata."""
from copy import deepcopy
from dataclasses import replace
import pytest
from suites.frontend.bpu.mbtb.transaction.types import (
    MbtbLookup,MbtbTraining,MbtbBranchFeedback,MbtbBatchTraining,MbtbPrediction,MbtbEntry)
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.mbtb.model.semantic import Events,coordinate,window,Target


def metadata(ways=4):
    return tuple(tuple(dict(rawHit=0,position=0,counter_value=0,
        **({'attribute':dict(branchType=0,rasAction=0)} if way<4 else {}))
        for way in range(ways)) for _ in range(2))


def branch(**changes):
    values=dict(target=0x80002340,taken=1,position=5,branch_type=3,ras_action=0,mispredict=1)
    values.update(changes);return MbtbBranchFeedback(**values)


@pytest.mark.parametrize('pc',(True,-1,1<<50,1.5,'pc'))
def test_lookup_rejects_out_of_domain_guarded_halfword_address(pc):
    with pytest.raises(ValueError):MbtbLookup(pc)


@pytest.mark.parametrize('pc',(0,1,(1<<49)-1,1<<49,(1<<50)-1))
def test_full_guarded_lookup_domain_is_not_narrowed_to_resolve_width_or_alignment(pc):
    assert MbtbLookup(pc).pc==pc and Events(pc=pc).pc==pc
    assert coordinate(pc)==((pc>>4)&1,(pc>>5)&3,(pc>>7)&255)
    assert window(pc)[(pc>>4)&1][0]==pc
    assert 0<=Target(7).at(pc)<(1<<50)


@pytest.mark.parametrize('field,bits',(('target',49),('taken',1),('position',5),
    ('branch_type',2),('ras_action',2),('mispredict',1)))
@pytest.mark.parametrize('bad',(-1,True,None,'1'))
def test_feedback_rejects_nonencoded_or_negative_values(field,bits,bad):
    with pytest.raises(ValueError):branch(**{field:bad})


@pytest.mark.parametrize('field,bits',(('target',49),('taken',1),('position',5),
    ('branch_type',2),('ras_action',2),('mispredict',1)))
def test_feedback_field_width_boundary(field,bits):
    with pytest.raises(ValueError):branch(**{field:1<<bits})
    assert getattr(branch(**{field:(1<<bits)-1}),field)==(1<<bits)-1


@pytest.mark.parametrize('kind',('guarded-resolve','empty','too-many','two-corrections',
    'duplicate-position','missing-meta','extra-meta-field','two-ways','partial-victim','fake-victim-attribute'))
def test_complete_feedback_shape_and_semantics_are_strict(kind):
    pc=0x80000000;meta=metadata();branches=(branch(),)
    if kind=='guarded-resolve':pc=1<<49
    elif kind=='empty':branches=()
    elif kind=='too-many':branches=(None,)*9
    elif kind=='two-corrections':branches+=(branch(position=6),)
    elif kind=='duplicate-position':branches+=(branch(mispredict=0),)
    elif kind=='missing-meta':meta[0][0].pop('rawHit')
    elif kind=='extra-meta-field':meta[0][0]['unknown']=0
    elif kind=='two-ways':meta=tuple(row[:2] for row in meta)
    elif kind=='partial-victim':meta=(metadata(5)[0],meta[1])
    else:
        meta=metadata(5);meta[0][4]['attribute']=dict(branchType=0,rasAction=0)
    with pytest.raises(ValueError):MbtbBatchTraining(pc,meta,branches)


@pytest.mark.parametrize('field,bits',(('rawHit',1),('position',5),('counter_value',2),
    ('branchType',2),('rasAction',2)))
def test_even_inactive_metadata_has_a_strict_encoded_domain(field,bits):
    meta=metadata();source=meta[1][3]
    if field in ('branchType','rasAction'):source=source['attribute']
    source[field]=1<<bits
    with pytest.raises(ValueError):MbtbBatchTraining(0,meta,(branch(),))


@pytest.mark.parametrize('ways',(4,5))
def test_feedback_is_detached_recursively_read_only_and_preserves_sparse_lanes(ways):
    meta=metadata(ways);branches=[branch(),None,branch(position=6,mispredict=0)]
    tx=MbtbBatchTraining(0x80000000,meta,branches);before=deepcopy(tx.meta_entries)
    meta[0][0]['attribute']['branchType']=1;branches[0]=None
    assert tx.meta_entries==before and tx.branches[0] is not None
    with pytest.raises(TypeError):tx.meta_entries[0][0]['rawHit']=1
    with pytest.raises(TypeError):tx.meta_entries[0][0]['attribute']['branchType']=1
    expected=expected_mbtb_feedback(tx)
    assert len(expected['meta_entries'][0])==4 and expected['resolved'][1] is None
    assert expected['resolved'][2]['position']==6


def test_prediction_snapshot_is_complete_detached_and_recursively_read_only():
    meta=metadata(5);p=MbtbPrediction(tuple(MbtbEntry(0,0,0,0,0,0) for _ in range(10)),meta)
    original=deepcopy(p.meta_entries);meta[0][0]['attribute']['branchType']=1
    assert p.meta_entries==original
    with pytest.raises(TypeError):p.meta_entries[0][0]['rawHit']=1
    with pytest.raises(ValueError):replace(p,entries=p.entries[:9])
    with pytest.raises(ValueError):replace(p,meta_entries=metadata(4))


def test_resolve_window_wraps_at_its_own_width_without_losing_the_top_legal_start():
    pc=(1<<49)-1;tx=MbtbBatchTraining(pc,metadata(),(branch(),))
    assert expected_mbtb_feedback(tx)['next_pc']==0
    single=MbtbTraining(pc,(1<<49)-1,1,31,3,metadata())
    assert single.pc==pc
