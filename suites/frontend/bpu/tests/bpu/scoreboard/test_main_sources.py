"""Independent composed learning and exact immutable source ownership."""
from dataclasses import replace

import pytest

from bpuverify.bpu.model.main_sources import BranchTargetSources,source_entries
from bpuverify.bpu.model.pipeline import Events,Outcome,Redirect,Resolution
from bpuverify.bpu.model.selection import Kind,StackAction
from tests.bpu.scoreboard.test_semantic_pipeline import PC,boot,published


ENABLED = (True,False,True,False,False,False,False)


def prepared():
    model,event = boot(BranchTargetSources())
    active = replace(event,enabled=ENABLED)
    for _ in range(3):model.advance(active)
    for _ in range(8):
        cycle = model.advance(active)
        if cycle.metadata is not None and cycle.metadata.lookup is not None:
            return model,active,cycle.metadata
    raise AssertionError('owned cold MainBTB request was not published')


def test_main_learning_uses_owned_request_metadata_and_commits_before_later_prediction():
    model,event,source = prepared()
    pc = source.pc
    target = pc+0x400
    outcome = Outcome(4,target,Kind.DIRECT,True,mispredict=True)
    feedback = Resolution(source.history,pc,(outcome,),origin=source)
    idle = replace(event,prediction_ready=False)
    for _ in range(4):model.advance(idle)
    model.advance(replace(idle,feedback=feedback))
    for _ in range(8):model.advance(idle)
    assert not model.sources.main_pending()
    assert model.sources.main.entry_commits==1
    model.advance(replace(idle,redirect=Redirect(source.history,pc+4,pc,True)))
    for _ in range(5):
        cycle = model.advance(event)
        token = cycle.tokens[1]
        if token is not None and token.pc==pc:
            assert cycle.decisions[1].branch.target==target
            assert cycle.decisions[1].branch.taken
            assert any(item.hit for row in source_entries(token.lookup) for item in row)
            break
    else:raise AssertionError('learned main prediction was not observed')


def test_read_frame_is_immutable_and_does_not_rebase_old_feedback_after_learning():
    model,event,source = prepared()
    before = source_entries(source.lookup)
    assert not any(item.hit for row in before for item in row)
    idle = replace(event,prediction_ready=False)
    for _ in range(4):model.advance(idle)
    model.advance(replace(idle,feedback=Resolution(source.history,source.pc,
        (Outcome(4,source.pc+0x400,Kind.DIRECT,True,mispredict=True),),origin=source)))
    for _ in range(8):model.advance(idle)
    assert source_entries(source.lookup)==before
    assert source_entries(model.sources.main.lookup_snapshot(source.pc))!=before


@pytest.mark.parametrize('fault',('missing','copy','foreign','retired'))
def test_numeric_pc_and_history_equivalence_cannot_replace_an_exact_learning_owner(fault):
    model,event,source = prepared()
    origin = None if fault=='missing' else replace(source) if fault=='copy' else source
    if fault=='foreign':
        other,_,origin = prepared()
        assert origin.pc==source.pc
    if fault=='retired':model.retire_source(source.sequence)
    feedback = Resolution(source.history if fault!='foreign' else origin.history,source.pc,
        (Outcome(4,source.pc+0x400,Kind.DIRECT,True,mispredict=True),),origin=origin)
    with pytest.raises(ValueError):model.advance(replace(event,feedback=feedback))


@pytest.mark.parametrize('index',(1,3,4,5,6))
def test_unsupported_enabled_learning_fails_instead_of_inventing_cold_results(index):
    model,event,source = prepared()
    enabled = list(ENABLED)
    enabled[index] = True
    active = replace(event,enabled=tuple(enabled))
    model.advance(active)
    model.advance(active)
    feedback = Resolution(source.history,source.pc,(),origin=source)
    with pytest.raises(NotImplementedError,match='further source-bank'):model.advance(replace(active,feedback=feedback))


@pytest.mark.parametrize('action',(StackAction.CALL,StackAction.RETURN,StackAction.RETURN_AND_CALL))
def test_stack_learning_requires_an_independently_composed_stack_model(action):
    model,event,source = prepared()
    feedback = Resolution(source.history,source.pc,
        (Outcome(4,source.pc+0x400,Kind.DIRECT,True,action,mispredict=True),),origin=source)
    with pytest.raises(NotImplementedError,match='return-stack adapter'):
        model.advance(replace(event,feedback=feedback))


def test_trained_live_enable_changes_are_not_silently_treated_as_qualified():
    model,event,source = prepared()
    idle = replace(event,prediction_ready=False)
    for _ in range(4):model.advance(idle)
    model.advance(replace(idle,feedback=Resolution(source.history,source.pc,
        (Outcome(4,source.pc+0x400,Kind.DIRECT,True,mispredict=True),),origin=source)))
    for _ in range(8):model.advance(idle)
    disabled = replace(idle,enabled=(True,False,False,False,False,False,False))
    model.advance(disabled)
    model.advance(disabled)
    with pytest.raises(NotImplementedError,match='live MainBTB enable transition'):
        model.advance(disabled)
