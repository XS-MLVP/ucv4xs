"""Real existing unit models compose through one independently owned token."""
from copy import deepcopy
from dataclasses import replace
import pytest
from suites.frontend.bpu.bpu.model.pipeline import Outcome,Resolution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources
from suites.frontend.bpu.bpu.model.indirect_sources import IndirectSources
from tests.bpu.scoreboard.test_semantic_pipeline import boot,PC
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit
from suites.frontend.bpu.bpu.model.joint_sources import JointLateSources

ENABLED=(False,False,True,True,False,True,False)
CONDITION,INDIRECT=2,10
CONDITION_TARGET,INDIRECT_TARGET,MAIN_WRONG=PC+0x200,PC+0x400,PC+0x600


def prepared():
    model,event=boot(JointLateSources())
    event=replace(event,enabled=ENABLED)
    for _ in range(12):
        cycle=model.advance(event)
        token=cycle.metadata
        if token is not None and token.lookup is not None:
            source=model.sources.target_snapshot(token,resolved=True)
            if source.prediction is not None:return model,event,token
    raise AssertionError('joint original source not published')


def resolve(model,event,source,*branches):
    idle=quiet(model,event)
    request=Resolution(source.history,source.pc,tuple(branches),origin=source)
    model.advance(replace(idle,feedback=request))
    quiet(model,event)
    return request


def outcome(position,target,kind,*,taken=True,wrong=False):
    return Outcome(position,target,kind,taken,mispredict=wrong)


def query(model,event,anchor):
    return revisit(model,event,anchor,PC)


def joint_learned():
    model,event,anchor=prepared()
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT,wrong=True))
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,taken=False,wrong=True),
            outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT))
    # A newly allocated weak NT provider may legitimately fall back to Main.
    # Real learning, not selector/table seeding, makes the direction decisive.
    source=query(model,event,anchor)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,taken=False),
            outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT))
    # A real Main-only lifetime distinguishes both retained late sources.
    idle=quiet(model,event)
    disabled=replace(event,enabled=(False,False,True,False,False,False,False))
    for _ in range(3):model.advance(replace(disabled,prediction_ready=False))
    source=query(model,disabled,anchor)
    resolve(model,disabled,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,taken=False),
            outcome(INDIRECT,MAIN_WRONG,Kind.INDIRECT,wrong=True))
    for _ in range(2):
        source=query(model,disabled,anchor)
        resolve(model,disabled,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    quiet(model,disabled)
    for _ in range(3):model.advance(replace(event,prediction_ready=False))
    return model,event,anchor,query(model,event,anchor)


def test_joint_metadata_reads_and_both_corrections_belong_to_one_original():
    model,event,anchor,source=joint_learned()
    bank=model.sources
    tagged=bank.snapshot(source,resolved=True)
    target=bank.target_snapshot(source,resolved=True)
    assert tagged.owner is target.owner is source.history
    assert tagged.read.pc==source.pc and target.read.pc==source.pc*2
    assert target.prediction.provider is not None and target.prediction.target==INDIRECT_TARGET*2
    assert target.prediction.confidence==3
    values=source.lookup.values()
    condition=next(slot for slot in range(4) if values.get(f'{slot}.valid') and values[f'{slot}.position']==CONDITION)
    assert values[f'{condition}.taken']==1
    assert dict(tagged.wanted)[f'{condition}.taken']==0
    assert tagged.late==target.late
    assert (tagged.late.branch.position,tagged.late.branch.target,tagged.late.source)==(INDIRECT,INDIRECT_TARGET,'indirect-history')


def test_conditional_taken_blocks_younger_target_and_cannot_train_it():
    model,event,anchor,source=joint_learned()
    before=deepcopy(model.sources.indirect.memories)
    confidence=model.sources.target_snapshot(source,resolved=True).prediction.confidence
    request=resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    assert model.sources.targets.feedback_for(request) is None
    fresh=query(model,event,anchor)
    # Promotion starts weak and still follows the old NT alternate. A second
    # real conditional outcome makes the promoted direction independently T.
    assert model.sources.snapshot(fresh,resolved=True).late.branch.position==INDIRECT
    request=resolve(model,event,fresh,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    assert model.sources.targets.feedback_for(request) is None
    fresh=query(model,event,anchor)
    late=model.sources.snapshot(fresh,resolved=True).late
    assert (late.branch.position,late.branch.target,late.source)==(CONDITION,CONDITION_TARGET,'main')
    assert model.sources.target_snapshot(fresh,resolved=True).prediction.confidence==confidence
    assert model.sources.indirect.memories==before


def test_all_four_existing_models_advance_once_per_nonreset_boundary(monkeypatch):
    model,event,_=prepared()
    bank=model.sources
    counts=dict.fromkeys(('main','micro','tage','indirect'),0)
    for name in counts:
        component=getattr(bank,name)
        original=component.advance
        def counted(*args,_name=name,_original=original,**kwargs):
            counts[_name]+=1
            return _original(*args,**kwargs)
        monkeypatch.setattr(component,'advance',counted)
    for _ in range(8):model.advance(event)
    assert counts==dict.fromkeys(counts,8)


def test_foreign_equal_checkpoint_cannot_borrow_either_original_source():
    model,event,anchor,source=joint_learned()
    clone=replace(source,history=replace(source.history))
    assert clone.history==source.history and clone.history is not source.history
    for snapshot in (model.sources.snapshot,model.sources.target_snapshot):
        with pytest.raises(ValueError,match='another checkpoint'):snapshot(clone,resolved=True)


def test_old_direction_and_target_metadata_do_not_rebase_after_new_learning():
    model,event,anchor,source=joint_learned()
    old=(deepcopy(model.sources.defined_metadata(source)),deepcopy(model.sources.defined_ittage_metadata(source)))
    reads=(model.sources.snapshot(source).read,model.sources.target_snapshot(source).read)
    resolve(model,event,source,outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True))
    query(model,event,anchor)
    assert (model.sources.defined_metadata(source),model.sources.defined_ittage_metadata(source))==old
    assert model.sources.snapshot(source).read is reads[0]
    assert model.sources.target_snapshot(source).read is reads[1]


def test_unexecuted_younger_feedback_is_rejected_before_either_model_learns():
    model,event,anchor,source=joint_learned()
    idle=quiet(model,event)
    before=(deepcopy(model.sources.main.state()),deepcopy(model.sources.tage.state()),deepcopy(model.sources.indirect.state()))
    request=Resolution(source.history,source.pc,(
        outcome(CONDITION,CONDITION_TARGET,Kind.CONDITIONAL,wrong=True),
        outcome(INDIRECT,INDIRECT_TARGET,Kind.INDIRECT)),origin=source)
    with pytest.raises(ValueError,match='unexecuted younger'):model.advance(replace(idle,feedback=request))
    assert (model.sources.main.state(),model.sources.tage.state(),model.sources.indirect.state())==before


def test_original_profiles_stay_fail_closed_and_new_profile_still_excludes_unimplemented_sources():
    assert 5 in DirectionSources.unsupported_learning
    assert 3 in IndirectSources.unsupported_learning
    assert JointLateSources.unsupported_learning==(1,4,6)
