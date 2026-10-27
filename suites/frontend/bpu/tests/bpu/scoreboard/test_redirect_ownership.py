"""Exact redirect-source contracts; synthetic cycles earn no DUT coverage."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.pipeline import environment
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.transaction.types import BpuRedirect
from tests.bpu.scoreboard.test_main_ownership import ready,input_bits
from tests.bpu.scoreboard.test_pipeline_checking import fixture_row


def request(source,*,target=None):
    pc=source.prediction.start_pc
    return BpuRedirect(pc+0x100 if target is None else target,source.meta.redirect,
        cfi_pc=pc+4,taken=1,branch_type=3)


def redirect_row(checker,event,source,tx):
    token=checker.source_token(source);payload=tx.payload()
    events=replace(event,redirect=Redirect(token.history,payload['cfi_pc'],payload['target'],bool(payload['taken'])))
    row=fixture_row(checker,events)
    row['inputs']['redirect'].update(kind=payload['branch_type'],action=payload['ras_action'])
    return row


def capture(checker,row):
    checker.capture(row,NS(tick=checker.last_tick+2));checker.raise_failure()


def owned_state(checker):
    return deepcopy((checker.model.state(),checker.model.sources.main.state(),
        checker.model.sources.micro.state(),checker.model.history.owned))


def test_redirect_keeps_the_exact_preverified_source_until_successful_acceptance():
    checker,event,source,_=ready();token=checker.source_token(source);tx=request(source)
    checker.plan_redirect(source,tx)
    with pytest.raises(ValueError,match='planned unaccepted redirect'):checker.retire_source(source.meta_tick)
    capture(checker,redirect_row(checker,event,source,tx))
    assert checker.last_events.redirect.source is token.history and not checker.redirect_plans
    checker.retire_source(source.meta_tick)
    assert token.sequence not in checker.model.published


@pytest.mark.parametrize('field',('pc','target','taken','kind','action','history','output','expired-owner'))
def test_bad_actual_redirect_latches_before_advancing_or_consuming_the_planned_owner(field):
    checker,event,source,_=ready();tx=request(source);checker.plan_redirect(source,tx)
    row=redirect_row(checker,event,source,tx)
    if field=='history':row['inputs']['redirect']['history']['phrLowBits']^=1
    elif field=='output':row['observed']['fires']=tuple(1-value for value in row['observed']['fires'])
    elif field=='expired-owner':checker.model.published.pop(checker.source_token(source).sequence)
    else:row['inputs']['redirect'][field]^=1
    before=owned_state(checker)
    with pytest.raises(AssertionError) as first:capture(checker,row)
    assert owned_state(checker)==before and len(checker.redirect_plans)==1
    with pytest.raises(AssertionError) as second:checker.finish()
    assert first.value is second.value


def test_redirect_metadata_is_checked_at_planning_and_copied_before_driving():
    checker,event,source,_=ready();tx=request(source)
    altered=deepcopy(tx.meta);altered['phr']['phrLowBits']^=1
    with pytest.raises(AssertionError):checker.plan_redirect(source,replace(tx,meta=altered))
    assert not checker.redirect_plans
    checker,event,source,_=ready();tx=request(source);checker.plan_redirect(source,tx)
    tx.meta['phr']['phrLowBits']^=1
    # The public driver payload changed, not the immutable planned owner.
    row=fixture_row(checker,event);payload=tx.payload()
    row['inputs']['redirect']=dict(valid=True,pc=payload['cfi_pc'],target=payload['target'],
        taken=payload['taken'],kind=payload['branch_type'],action=payload['ras_action'],history=payload['meta']['phr'])
    with pytest.raises(AssertionError):capture(checker,row)
    assert len(checker.redirect_plans)==1


def test_unaccepted_redirect_is_not_silently_dropped_and_reset_cancels_ownership():
    checker,event,source,_=ready();checker.plan_redirect(source,request(source))
    with pytest.raises(AssertionError,match='redirect was not accepted'):checker.finish()
    capture(checker,fixture_row(checker,replace(event,reset=True)))
    assert not checker.redirect_plans and not checker.source_receipts
    with pytest.raises(AssertionError):checker.source_token(source)


def test_redirect_acceptance_must_follow_planned_order():
    checker,event,source,_=ready();first=request(source);second=request(source,target=first.pc+16)
    checker.plan_redirect(source,first);checker.plan_redirect(source,second)
    before=owned_state(checker)
    with pytest.raises(AssertionError):capture(checker,redirect_row(checker,event,source,second))
    assert owned_state(checker)==before and len(checker.redirect_plans)==2


def test_same_cycle_feedback_and_redirect_keep_their_independent_original_owner():
    checker,event,source,training=ready();token=checker.source_token(source);tx=request(source)
    checker.plan_redirect(source,tx);checker.plan_feedback(source,training)
    row=redirect_row(checker,event,source,tx);row['inputs']['training']=input_bits(source,training)
    capture(checker,row)
    assert checker.last_events.redirect.source is token.history
    assert checker.last_resolution[1].origin is token
    assert not checker.redirect_plans and not checker.feedback_plans


@pytest.mark.parametrize('explicit',(False,True))
def test_numeric_history_alias_requires_an_explicit_owner_not_latest_or_oldest_guessing(explicit):
    checker,event,source,_=ready();token=checker.source_token(source);tx=request(source)
    # Test-only ambiguity fixture. Build an alternative history by semantic
    # taken-edge events: one differing path word, then shifts that hide it
    # from the 13-bit encoding. This is NOT a native FTQ legality proof.
    history=checker.model.history
    for edge in range(52):
        checkpoint=history.advance(taken=True,cfi_pc=0,target=2 if edge==40 else 0,
            restore=token.history if edge==0 else None)
    assert checkpoint.metadata()==token.history.metadata() and checkpoint.history!=token.history.history
    alias=replace(token,sequence=max(checker.model.published)+1,history=checkpoint)
    checker.model.published[alias.sequence]=alias
    row=redirect_row(checker,event,source,tx)
    with pytest.raises(ValueError,match='aliases different history owners'):
        environment(row['inputs'],checker.model)
    if explicit:
        checker.plan_redirect(source,tx);capture(checker,row)
        assert checker.last_events.redirect.source is token.history
        assert checker.last_events.redirect.source is not checkpoint and not checker.redirect_plans
    else:
        before=owned_state(checker)
        with pytest.raises(ValueError,match='aliases different history owners'):capture(checker,row)
        assert owned_state(checker)==before
