"""Own MainBTB/TAGE state and checkpoint-derived lookup/feedback identity."""
from suites.frontend.bpu.models.configuration import TAGE_ALLOCATION_WAIT
from copy import deepcopy
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources,context_for
from suites.frontend.bpu.bpu.model.pipeline import Outcome,Resolution,Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_semantic_pipeline import boot,PC


ENABLED = (False,False,True,True,False,False,False)


def prepared(*,sources_factory=DirectionSources,initial_pc=PC):
    model,event = boot(sources_factory(),pc=initial_pc)
    active = replace(event,enabled=ENABLED)
    for _ in range(8):
        cycle = model.advance(active)
        if cycle.metadata is not None and cycle.metadata.lookup is not None:
            return model,active,cycle.metadata
    raise AssertionError('owned source not published')


def quiet(model,event):
    idle = replace(event,prediction_ready=False)
    for _ in range(16):
        model.advance(idle)
        if model.stages[1:]==(None,None) and not model.sources.main_pending():return idle
    raise AssertionError('semantic writes did not commit')


def revisit(model,event,anchor,pc):
    idle = quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,pc,True,Kind.INDIRECT)))
    for _ in range(8):
        cycle = model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==pc:return cycle.metadata
    raise AssertionError('semantic new source did not retire')


def resolve(model,event,source,taken,*,wrong,owner=None):
    idle = quiet(model,event)
    resolution = Resolution(source.history,source.pc,(Outcome(4,source.pc+0x400,Kind.CONDITIONAL,taken,mispredict=wrong),),origin=source)
    if owner is not None:
        feedback = model.sources.feedback_for(resolution)
        for _ in range(TAGE_ALLOCATION_WAIT):
            if model.sources.tage.allocation_at_next_accept(feedback)==owner:break
            model.advance(idle)
        else:raise AssertionError('owned allocation forecast did not recur')
    model.advance(replace(idle,feedback=resolution))
    quiet(model,event)
    return resolution


def learned():
    model,event,anchor = prepared()
    resolve(model,event,anchor,True,wrong=True)
    source = revisit(model,event,anchor,anchor.pc)
    resolve(model,event,source,False,wrong=True,owner=(2,0))
    source = revisit(model,event,anchor,anchor.pc)
    resolve(model,event,source,False,wrong=False)
    return model,event,anchor,revisit(model,event,anchor,anchor.pc)


def meta(model,source):
    return model.sources.defined_metadata(source)


def test_owned_history_and_main_frames_create_learning_without_observed_provider_inputs():
    model,event,anchor,source = learned()
    values = meta(model,source)
    provider = next(slot for slot in range(4) if values.get(f'{slot}.hasProvider'))
    assert tuple(values[f'{provider}.{field}'] for field in ('providerTableIdx','providerWayIdx','providerTakenCtr_value'))==(2,0,2)
    assert model.sources.snapshot(source).read.context==context_for(source.history)
    assert source.middle.branch.taken is False
    assert model.sources.snapshot(source,resolved=True).late.branch.taken is False
    feedback = model.sources.feedback_for(Resolution(source.history,source.pc,
        (Outcome(4,source.pc+0x400,Kind.CONDITIONAL,True,mispredict=True),),origin=source))
    assert feedback.context==context_for(source.history)
    assert feedback.branches[0].hint.table==2 and feedback.branches[0].hint.way==0


def test_provider_promotion_freezes_s2_raw_and_s3_qualified_alternate_for_the_same_owner():
    model,event,anchor,source = learned()
    resolve(model,event,source,True,wrong=True,owner=(3,0))
    weak = revisit(model,event,anchor,anchor.pc)
    values = meta(model,weak)
    slot = next(slot for slot in range(4) if values.get(f'{slot}.hasProvider'))
    assert tuple(values[f'{slot}.{field}'] for field in ('providerTableIdx','providerTakenCtr_value','hasAlt','useProvider','altOrBasePred'))==(3,4,1,0,0)
    assert weak.middle.branch.taken and weak.middle_corrected
    assert not model.sources.snapshot(weak,resolved=True).late.branch.taken
    resolve(model,event,weak,True,wrong=True)
    strong = revisit(model,event,anchor,anchor.pc)
    values = meta(model,strong)
    assert values[f'{slot}.providerTakenCtr_value']==5 and values[f'{slot}.useProvider']==1
    assert model.sources.snapshot(strong,resolved=True).late.branch.taken


def test_old_read_and_feedback_do_not_rebase_after_new_writes_or_selector_changes():
    model,event,anchor,source = learned()
    before = deepcopy(meta(model,source))
    read = model.sources.snapshot(source).read
    resolve(model,event,source,True,wrong=True,owner=(3,0))
    new = revisit(model,event,anchor,anchor.pc)
    assert meta(model,source)==before and model.sources.snapshot(source).read is read
    frozen = model.sources.snapshot(new,resolved=True)
    # Fault qualification of S3's freeze boundary, not a DUT state seed.
    model.sources.tage.selectors[:] = [0]*8
    assert model.sources.snapshot(new,resolved=True) is frozen
    assert not frozen.late.branch.taken
    assert model.sources.feedback_for(Resolution(source.history,source.pc,(),origin=source)).context==read.context


def test_owned_snapshot_registry_releases_flushed_and_explicitly_retired_sources():
    model,event,anchor,source = learned()
    expected = {token.history.sequence for token in (*model.stages,*model.published.values()) if token is not None}
    assert set(model.sources.reads)==expected
    key = source.history.sequence
    model.retire_source(source.sequence)
    assert key not in model.sources.reads and key not in model.sources.resolved
    with pytest.raises(ValueError,match='absent, retired'):model.sources.snapshot(source)
    model.advance(replace(event,reset=True))
    assert not model.sources.reads and not model.sources.resolved


def test_foreign_equal_checkpoint_cannot_borrow_an_owned_tage_frame():
    model,event,anchor,source = learned()
    forged = replace(source,history=replace(source.history))
    assert forged.history==source.history and forged.history is not source.history
    with pytest.raises(ValueError,match='another checkpoint'):model.sources.snapshot(forged)


def test_public_tage_lookup_snapshot_is_pure_and_immutable():
    model,event,anchor,source = learned()
    state = deepcopy(model.sources.tage.state())
    read = model.sources.tage.lookup_snapshot(source.pc,context_for(source.history))
    assert model.sources.tage.state()==state
    old = read.entries
    resolve(model,event,source,True,wrong=True,owner=(3,0))
    assert read.entries==old and model.sources.tage.lookup_snapshot(source.pc,read.context).entries!=old
