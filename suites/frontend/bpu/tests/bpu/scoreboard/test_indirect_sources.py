"""Independent semantic composition; these synthetic tests are not DUT credit."""
from bpuverify.common.model.configuration import ITTAGE_ALLOCATION_WAIT

from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.model.indirect_sources import IndirectSources,allocation,context_for
from bpuverify.bpu.model.ittage_service import PC,POSITION,PATHS,TARGETS,STREAM_PC,pending_plan
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.tage.model.semantic import lfsr_next
from tests.bpu.scoreboard.test_semantic_pipeline import boot
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit

ENABLED=(False,False,True,False,False,True,False)


def prepared():
    model,event=boot(IndirectSources());event=replace(event,enabled=ENABLED)
    for _ in range(10):
        cycle=model.advance(event)
        token=cycle.metadata
        if token is not None and token.lookup is not None and model.sources.snapshot(token,resolved=True).prediction is not None:
            return model,event,token
    raise AssertionError('enabled independent indirect source was not published')


def query_path(model,event,anchor,path,*,stream=False):
    if not stream:
        middle=anchor if path is None else revisit(model,event,anchor,path)
        return revisit(model,event,middle,PC)
    middle=anchor
    for pc in ((PC,) if path is None else (path,PC)):
        model.advance(replace(event,redirect=Redirect(middle.history,middle.pc+4,pc,True)))
        for _ in range(10):
            cycle=model.advance(event)
            if cycle.metadata is not None and cycle.metadata.pc==pc:
                middle=cycle.metadata;break
        else:raise AssertionError('continuous semantic query did not publish')
    return middle


def resolution(source,target,*,wrong=False,kind=Kind.INDIRECT):
    return Resolution(source.history,source.pc,(Outcome(POSITION,target,kind,True,mispredict=wrong),),origin=source)


def resolve(model,event,source,target,*,wrong=True,kind=Kind.INDIRECT):
    idle=quiet(model,event);request=resolution(source,target,wrong=wrong,kind=kind)
    model.advance(replace(idle,feedback=request));quiet(model,event)
    return request


def establish(table):
    model,event,anchor=prepared()
    for path,target in zip(PATHS,TARGETS,strict=True):
        for _ in range(ITTAGE_ALLOCATION_WAIT):
            source=query_path(model,event,anchor,path)
            expected=model.sources.snapshot(source,resolved=True)
            if expected.prediction.provider is None and expected.allocation==table:break
            model.retire_source(source.sequence)
        else:raise AssertionError('independent cold allocation opportunity missing')
        assert expected.late.branch.target!=target
        resolve(model,event,source,target)
    originals=tuple(query_path(model,event,anchor,path) for path in PATHS)
    return model,event,anchor,originals


def pending_program(table):
    model,event,anchor,originals=establish(table)
    loop=revisit(model,event,anchor,STREAM_PC)
    resolve(model,event,loop,STREAM_PC,kind=Kind.DIRECT)
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,STREAM_PC,True)))
    for _ in range(8):model.advance(event)
    baseline=model.sources.indirect.commits
    requests=tuple(resolution(source,target) for source,target in zip(originals,TARGETS,strict=True))
    for request in requests:model.advance(replace(event,feedback=request))
    for _ in range(16):
        cycle=model.advance(event)
        assert cycle.fires[1] and cycle.tokens[0].pc%2==PC%2
        indirect=model.sources.indirect
        if indirect.learning is None and not indirect.normal:break
    else:raise AssertionError('indirect learning did not mature under read pressure')
    return model,event,anchor,originals,requests,baseline


@pytest.mark.parametrize('table',(0,2))
def test_four_real_history_owners_keep_complete_foreign_targets_old_until_actual_service(table):
    model,event,anchor,originals,_,baseline=pending_program(table)
    sources=model.sources;indirect=sources.indirect
    reads=tuple(sources.snapshot(token,resolved=True).read for token in originals)
    assert len({read.context for read in reads})==4
    assert tuple(read.entries[table].target.pointer for read in reads)==(0,1,2,3)
    frozen=tuple(deepcopy(sources.defined_ittage_metadata(token)) for token in originals)
    plan=pending_plan(indirect,table,PC%2)
    assert len(plan)==4 and tuple(p['confidence'] for p in plan)==(3,)*4
    assert tuple(p['pointer'] for p in plan)==(0,1,2,3)
    assert indirect.commits==baseline and indirect.caches[table][PC%2].overwrites==0
    for path,target in zip(PATHS,TARGETS,strict=True):
        old=query_path(model,event,anchor,path,stream=True)
        prediction=sources.snapshot(old,resolved=True).prediction
        assert (prediction.provider,prediction.confidence,prediction.target)==(table,2,target*2)
        assert pending_plan(indirect,table,PC%2)==plan and indirect.commits==baseline
    quiet(model,event)
    assert indirect.commits==baseline+4 and pending_plan(indirect,table,PC%2)==()
    for path,target in zip(PATHS,TARGETS,strict=True):
        new=query_path(model,event,anchor,path)
        prediction=sources.snapshot(new,resolved=True).prediction
        assert (prediction.provider,prediction.confidence,prediction.target)==(table,3,target*2)
    assert tuple(sources.defined_ittage_metadata(token) for token in originals)==frozen
    assert tuple(indirect.regions.regions[:4])==tuple(target*2>>20 for target in TARGETS)


def test_nonzero_confidence_retains_target_then_zero_confidence_relearns_without_metadata_feedback_seeding():
    model,event,anchor=prepared();pc=anchor.pc
    # Pick by independent PRNG, never by an observed allocation proposal.
    for _ in range(ITTAGE_ALLOCATION_WAIT):
        source=revisit(model,event,anchor,pc)
        if model.sources.snapshot(source,resolved=True).allocation==4:break
    else:raise AssertionError('long history admission absent')
    first,second=pc+0x400,pc+0x600
    for target,confidence,expected in ((first,2,first),(second,1,first),(second,0,first),(second,0,second)):
        resolve(model,event,source,target)
        source=revisit(model,event,anchor,pc)
        actual=model.sources.snapshot(source,resolved=True)
        assert (actual.prediction.provider,actual.prediction.confidence,actual.prediction.target)==(4,confidence,expected*2)
        assert actual.late.branch.target==expected
        assert model.sources.feedback_for(resolution(source,target)).context==context_for(source.history)


def test_owned_sram_read_is_at_s1_accept_not_at_s0_issue():
    model,event,anchor=prepared();idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,PC,True)))
    token=model.stages[0]
    assert model.sources.snapshot(token).read is None
    model.advance(idle)
    assert model.sources.snapshot(token).read is None
    model.advance(event)
    assert model.sources.snapshot(token).read==model.sources.indirect.lookup_snapshot(PC*2,context_for(token.history))


@pytest.mark.parametrize('reset',(False,True))
def test_free_running_allocation_prng_predicts_sample_phase_even_without_a_transfer(reset):
    model,event,_=prepared();source=model.sources
    idle=quiet(model,event);before=source.random
    inputs=replace(idle,consumed_reset=reset)
    assert source.random_at_sample(inputs)==(1 if reset else lfsr_next(before))
    model.advance(inputs)
    assert source.random==(1 if reset else lfsr_next(before))


@pytest.mark.parametrize('mask',range(8))
def test_allocation_prefers_lowest_random_enabled_candidate_then_lowest_legal(mask):
    from types import SimpleNamespace as NS
    candidates=(0,2);preferred=tuple(t for t in candidates if mask&(1<<t))
    assert allocation(NS(candidates=candidates),mask)==min(preferred or candidates)
    assert allocation(NS(candidates=()),mask) is None


@pytest.mark.parametrize('fault',('foreign','retired','reset'))
def test_equal_numeric_history_cannot_borrow_or_reanimate_an_independent_source(fault):
    model,event,source=prepared()
    if fault=='foreign':source=replace(source,history=replace(source.history))
    elif fault=='retired':model.retire_source(source.sequence)
    else:model.advance(replace(event,reset=True))
    with pytest.raises(ValueError,match='absent, retired|another checkpoint'):
        model.sources.snapshot(source,resolved=True)


def test_pure_lookup_and_region_selection_are_separate_and_frozen_predictions_do_not_rebase():
    model,event,anchor,sources=establish(2);indirect=model.sources.indirect;token=sources[0]
    before=deepcopy(indirect.state());read=indirect.lookup_snapshot(PC*2,context_for(token.history))
    selected=indirect.predict_snapshot(read)
    assert indirect.state()==before and indirect.inspect(PC*2,read.context)==selected
    original=model.sources.snapshot(token,resolved=True)
    pointer=read.entries[2].target.pointer
    # Synthetic fault qualification: S1 snapshot owns SRAM bits; the region
    # directory is selected at S2, whereas a completed S3 must remain frozen.
    indirect.regions._regions[pointer]+=1
    assert indirect.predict_snapshot(read).target==selected.target+(1<<20)
    assert model.sources.snapshot(token,resolved=True) is original
    assert original.prediction.target==selected.target
    with pytest.raises(TypeError):indirect.predict_snapshot(token)
