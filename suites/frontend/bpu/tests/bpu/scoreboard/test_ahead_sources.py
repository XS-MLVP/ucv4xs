"""Ahead reads and fast learning derive from owned normal/recovery events."""
from dataclasses import replace
import pytest

from bpuverify.bpu.model.ahead_sources import AheadSources,history_feature
from bpuverify.bpu.model.pipeline import Events,Outcome,Redirect,Resolution
from bpuverify.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_semantic_pipeline import boot


PC=0x40000800
OTHER=PC+0x226
ENABLED=(False,True,True,False,False,False,False)


def quiet(model,event):
    idle=replace(event,prediction_ready=False)
    for _ in range(128):
        model.advance(idle)
        if model.stages[1:]==(None,None) and not model.sources.main_pending():return idle
    raise AssertionError('independent BTB obligations did not quiesce')


def query(model,event,anchor,pc):
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,pc,True)))
    for _ in range(32):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.pc==pc:
            quiet(model,event)
            return cycle.metadata
    raise AssertionError(('owned ahead query did not retire',pc))


def prepared(kind=Kind.INDIRECT):
    model,event=boot(AheadSources());event=replace(event,enabled=ENABLED)
    anchor=None
    for _ in range(16):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.lookup is not None:
            anchor=cycle.metadata;break
    assert anchor is not None
    sources=[]
    for pc,position,target in ((PC,4,OTHER),(OTHER,9,PC)):
        source=query(model,event,anchor,pc);sources.append(source)
        idle=quiet(model,event)
        request=Resolution(source.history,pc,(Outcome(position,target,kind,True,mispredict=True),),origin=source)
        model.advance(replace(idle,feedback=request));quiet(model,event)
    return model,event,anchor,tuple(sources)


@pytest.mark.parametrize('kind',(Kind.DIRECT,Kind.INDIRECT))
def test_independent_two_branch_loop_learns_ahead_reads_and_consumes_both_real_targets(kind):
    model,event,anchor,originals=prepared(kind)
    idle=quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,PC,True)))
    consumed=set();repairs=0
    for _ in range(256):
        cycle=model.advance(event)
        repairs+=int(cycle.middle_repair)
        if cycle.tokens[0] is not None and cycle.fires[1] and not cycle.flushes[0] and cycle.decisions[0].source=='ahead':
            token=cycle.tokens[0];consumed.add(token.pc)
            assert cycle.decisions[0].branch.target=={PC:OTHER,OTHER:PC}[token.pc]
        if consumed=={PC,OTHER}:break
    else:raise AssertionError(('ahead did not learn both semantic loop edges',consumed,model.sources.ahead.state()))
    assert repairs and model.sources.ahead.commits>=2
    assert all(not any(model.sources.snapshot(token).frame.hits) for token in originals if model.sources.snapshot(token).frame is not None)


def test_ahead_index_feature_uses_the_owned_six_bit_history_fold_not_the_new_path():
    model,event,anchor,_=prepared()
    assert history_feature(anchor.history)==anchor.history.folds()[2]%16
    idle=quiet(model,event)
    cycle=model.advance(replace(idle,redirect=Redirect(anchor.history,PC+4,OTHER,True)))
    assert model.sources.last_ahead_events.history==history_feature(anchor.history)
    assert model.sources.last_ahead_events.read_pc==OTHER
    assert model.stages[0].history.history!=anchor.history.history


def test_conditional_learning_is_not_silently_modelled_as_microtage_misses():
    model,event,anchor,_=prepared();idle=quiet(model,event)
    request=Resolution(anchor.history,anchor.pc,(Outcome(4,PC,Kind.CONDITIONAL,True,mispredict=True),),origin=anchor)
    with pytest.raises(NotImplementedError,match='MicroTAGE'):model.advance(replace(idle,feedback=request))


@pytest.mark.parametrize('fault',('copied','foreign','retired'))
def test_old_ahead_snapshot_cannot_be_borrowed_by_another_checkpoint(fault):
    model,event,anchor,_=prepared()
    token=replace(anchor,history=replace(anchor.history)) if fault=='copied' else anchor
    if fault=='foreign':token=prepared()[2]
    elif fault=='retired':model.retire_source(anchor.sequence)
    with pytest.raises(ValueError,match='checkpoint'):model.sources.snapshot(token)
