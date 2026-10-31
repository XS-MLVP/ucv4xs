"""Short direction learning comes from real owned branch paths, not signals."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from suites.frontend.bpu.bpu.model.early_direction_sources import EarlyDirectionSources,EarlySnapshot,context
from suites.frontend.bpu.bpu.model.pipeline import Redirect,Resolution,Outcome
from suites.frontend.bpu.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_ahead_sources import ENABLED,quiet,query
from tests.bpu.scoreboard.test_semantic_pipeline import boot
from suites.frontend.bpu.utage.model.semantic import Base,tag


def prepare(pc=0x40000000):
    model,event=boot(EarlyDirectionSources(),pc=pc);event=replace(event,enabled=ENABLED)
    for _ in range(16):
        cycle=model.advance(event)
        if cycle.metadata is not None and cycle.metadata.lookup is not None:anchor=cycle.metadata;break
    else:raise AssertionError('owned cold Main source did not retire')
    source=query(model,event,anchor,pc)
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=Resolution(source.history,pc,(Outcome(2+(pc&8),pc,Kind.CONDITIONAL,True,mispredict=True),),origin=source)))
    quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(anchor.history,anchor.pc+4,pc,True)))
    latest=source
    for _ in range(32):
        cycle=model.advance(event);token=cycle.metadata
        if token is not None and token.pc==pc:latest=token
        if any(bank.outstanding for bank in model.sources.ahead.pending):
            quiet(model,event)
            query(model,event,latest,pc)
            for _ in range(32):
                owned=model.advance(event).metadata
                if owned is not None and owned.pc==pc and owned.early.source=='ahead':
                    assert owned.early.branch.position==2+(pc&8)
                    quiet(model,event);return model,event,latest,owned
            raise AssertionError('committed Ahead provider did not reach a new owned consumer')
    raise AssertionError('independent Ahead conditional source did not become visible')


@pytest.mark.parametrize('pc',(0x40000000,0x40000800))
def test_conditional_ahead_learning_and_short_negative_provider_are_independently_composed(pc):
    model,event,anchor,source=prepare(pc)
    idle=quiet(model,event)
    before=model.sources.short_snapshot(source)
    request=Resolution(source.history,pc,(Outcome(2,pc,Kind.CONDITIONAL,False,mispredict=True),),origin=source)
    model.advance(replace(idle,feedback=request));quiet(model,event)
    fallback=query(model,event,source,pc)
    idle=quiet(model,event)
    model.advance(replace(idle,feedback=Resolution(fallback.history,pc,
        (Outcome(4,pc,Kind.DIRECT,True,mispredict=True),),origin=fallback)))
    quiet(model,event)
    model.advance(replace(idle,redirect=Redirect(fallback.history,pc+4,pc,True)))
    learned=False;consumed=False
    for _ in range(256):
        cycle=model.advance(event);short=model.sources.short
        learned|=bool(any(cache.recent for cache in short.updates))
        token=cycle.metadata
        if token is not None and token.pc==pc:
            snapshot=model.sources.short_snapshot(token);values=snapshot.prediction.values()
            if any(values.get(f'{way}.hit') and not values.get(f'{way}.taken') for way in range(4)):
                consumed=True
                assert token.early.branch.position!=2 or not token.early.branch.taken
                break
    assert learned and consumed
    assert model.sources.short_snapshot(source)==before


@pytest.mark.parametrize('fault',('copied','foreign','retired'))
def test_short_history_snapshot_requires_the_exact_live_checkpoint_owner(fault):
    model,event,anchor,source=prepare()
    if fault=='copied':source=replace(source,history=replace(source.history))
    elif fault=='foreign':source=prepare()[3]
    else:model.retire_source(source.sequence)
    with pytest.raises(ValueError,match='checkpoint'):model.sources.short_snapshot(source)


def test_original_early_path_end_qualifies_training_not_the_final_main_end():
    model,event,anchor,source=prepare()
    saved=model.sources.short_snapshot(source)
    # Synthetic pure-model boundary: both conditional source positions exist,
    # but only the original early path's prefix may later train.
    frame=replace(saved.prediction.frame,positions=(1,2,6,7))
    prediction=replace(saved.prediction,frame=frame,bases=tuple(Base(True,p,True,1,False) for p in frame.positions),redirect_bubble=False)
    model.sources.short_reads[source.history.sequence]=EarlySnapshot(source.history,prediction,2)
    raw=model.sources.defined_short_metadata(source,qualified=False)
    qualified=model.sources.defined_short_metadata(source)
    assert tuple(raw[f'{way}.valid'] for way in range(4))==(1,1,1,1)
    assert tuple(qualified[f'{way}.valid'] for way in range(4))==(1,1,0,0)
    final=replace(source.early,branch=replace(source.early.branch,position=7))
    feedback=model.sources.short_feedback(source,final)
    assert tuple(item.valid for item in feedback.sources)==(True,True,False,False)
    assert feedback.position==7


@pytest.mark.parametrize('winner',('normal','redirect','s2','s3'))
def test_read_tag_and_repair_histories_keep_their_distinct_owned_ancestry(winner):
    model,event,anchor,source=prepare()
    quiet(model,event)
    first=source;second=anchor
    third=next(token for token in model.published.values() if token.history is not first.history
        and token.history is not second.history and model.sources.short_snapshot(token).prediction.frame is not None)
    decisions=tuple(source.early for _ in range(3))
    cycle=NS(tokens=(first,second,third),decisions=decisions,final_repair=winner=='s3',
        middle_repair=winner in ('s2','s3'),next_pc=source.pc,fires=(False,False,False,False),
        flushes=(False,False,False),enabled=ENABLED)
    request=replace(event,redirect=Redirect(anchor.history,anchor.pc+4,source.pc,True)) if winner=='redirect' else event
    # Observe the arguments emitted to the semantic component, not any DUT IO.
    model.sources.advance(request,cycle,None)
    expected=anchor.history if winner=='redirect' else third.history if winner=='s3' else second.history if winner=='s2' else first.history
    assert model.sources.last_short_events.read_context==context(expected)
    assert model.sources.last_short_events.context==context(first.history)
    assert model.sources.last_short_events.override_context==context(third.history if winner=='s3' else second.history if winner=='s2' else None)


def test_live_read_positions_do_not_rebase_the_immutable_original_fasttrain():
    model,event,anchor,source=prepare()
    saved=model.sources.short_snapshot(source)
    before=model.sources.short_feedback(source,source.middle)
    query(model,event,source,source.pc+0x222)
    assert model.sources.short_snapshot(source) is saved
    assert model.sources.short_feedback(source,source.middle)==before
    assert before.indices==saved.prediction.frame.read.indices
    assert before.context==saved.prediction.frame.context


def test_disable_at_retirement_still_offers_original_fasttrain_before_next_cycle_admission():
    model,event,anchor,source=prepare()
    off=replace(event,enabled=(False,False,True,False,False,False,False))
    observed=False
    for _ in range(32):
        cycle=model.advance(off)
        if not cycle.enabled[1] and cycle.tokens[2] is not None:
            expected=model.sources.short_feedback(cycle.tokens[2],cycle.decisions[2])
            assert expected is not None
            assert model.sources.last_short_events.feedback==expected
            assert model.sources.short.offered==expected
            observed=True;break
    assert observed


def test_pending_logical_learning_is_distinct_from_continuously_read_blocked_sram_retirement():
    model,event,anchor,source=prepare()
    sources=model.sources
    # A real S3 offer keeps pause busy until admission and learning mature.
    for _ in range(32):
        cycle=model.advance(event)
        if cycle.metadata is not None and sources.short.offered is not None:break
    assert sources.main_pending()
    quiet(model,event)
    assert sources.short.offered is None and sources.short.learning is None
    assert not sources.main_pending()


def test_reset_and_explicit_retirement_release_both_owned_early_source_banks():
    model,event,anchor,source=prepare()
    key=source.history.sequence
    assert key in model.sources.ahead_reads and key in model.sources.short_reads
    model.retire_source(source.sequence)
    assert key not in model.sources.ahead_reads and key not in model.sources.short_reads
    model.advance(replace(event,reset=True))
    assert not model.sources.short_reads and not model.sources.ahead_reads
    assert model.sources.short.frame is None and model.sources.short.memory==[{},{}]


def test_full_configured_tag_width_is_not_normalized_to_the_implementation_container():
    model,event,anchor,source=prepare(0x40000008)
    saved=model.sources.short_snapshot(source)
    assert tag(source.pc,saved.prediction.frame.context,0)>=128
    assert tag(source.pc,saved.prediction.frame.context,0)!=tag(source.pc,saved.prediction.frame.context,0)%128
