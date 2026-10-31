"""Source and full-input discriminators; none provide hardware coverage."""
from copy import deepcopy
from dataclasses import replace
import pytest
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback
from suites.frontend.bpu.bpu.model.window_lifetime import WindowLifetimes,LifetimeError,freeze
from suites.frontend.bpu.bpu.model.feedback_gate import FeedbackGate,wire_payload

PC=0x40000800
PROJECTION={'history':{'phrPtr':{'flag':0,'value':0},'phrLowBits':0},'main':({'hit':0},)}
META={'phr':{'phrLowBits':0},'full_wide_field':(1<<65)+7,'unused_predictor':{'bit':1}}


def transaction(*,metadata=None,pc=PC):
    return BpuBatchTraining(pc,deepcopy(META if metadata is None else metadata),
        (BpuBranchFeedback(1,PC+0x800,3,mispredict=1),))


def source(ledger,gate,*,pc=PC,meta=None):
    result=ledger.admit(pc,metadata=PROJECTION)
    gate.remember(result,META if meta is None else meta)
    return result


def setup(capacity=3):
    ledger=WindowLifetimes(capacity);gate=FeedbackGate(ledger)
    return ledger,gate,source(ledger,gate)


def prepare(gate,original,tx=None):
    tx=transaction() if tx is None else tx
    gate.prepare(original,tx,receipt_metadata=META)
    return tx


def accept(gate,tx):
    gate.admit(tx)
    return gate.accept(deepcopy(wire_payload(tx)),projection=deepcopy(PROJECTION))


def test_younger_then_older_same_PC_and_equal_metadata_are_distinct_legal_inputs():
    ledger,gate,old=setup();young=source(ledger,gate)
    accept(gate,prepare(gate,young));accept(gate,prepare(gate,old))
    assert [t.source for t in ledger.accepted]==[young,old]
    assert gate.launches==gate.accepts==2 and ledger.active==[old,young]


def test_flushed_original_is_rejected_before_an_input_can_be_prepared():
    ledger,gate,anchor=setup();old=source(ledger,gate)
    ledger.redirect(anchor)
    with pytest.raises(LifetimeError,match='flushed'):prepare(gate,old)
    assert gate.pending is None and gate.launches==gate.accepts==0


def test_original_invalidated_between_preparation_and_driver_launch_cannot_write():
    ledger,gate,anchor=setup();old=source(ledger,gate)
    tx=prepare(gate,old);ledger.redirect(anchor)
    with pytest.raises(LifetimeError,match='invalidated before driver'):gate.admit(tx)
    assert gate.launches==gate.accepts==0
    gate.cancel_unlaunched();assert gate.pending is None


@pytest.mark.parametrize('reset_gate',(False,True))
def test_reset_ends_old_prepared_qualification_even_if_the_receipt_still_exists(reset_gate):
    ledger,gate,old=setup();tx=prepare(gate,old)
    ledger.reset()
    if reset_gate:gate.reset()
    with pytest.raises(LifetimeError):gate.admit(tx)
    assert gate.launches==gate.accepts==0


def test_cached_original_survives_commit_and_slot_reuse_without_rebinding_metadata():
    ledger,gate,old=setup(1);tx=prepare(gate,old)
    ledger.commit(old)
    fresh=source(ledger,gate,meta={'other':'original'})
    result=accept(gate,tx)
    assert result.source is old and ledger.slots[old.slot] is fresh


def test_commit_without_reuse_can_still_qualify_the_original_queued_resolve():
    ledger,gate,old=setup(1);ledger.commit(old)
    result=accept(gate,prepare(gate,old))
    assert result.source is old and not ledger.active


def test_uncached_original_cannot_borrow_a_reused_metadata_position():
    ledger,gate,old=setup(1);ledger.commit(old)
    source(ledger,gate,meta={'new':1})
    with pytest.raises(LifetimeError,match='another generation'):prepare(gate,old)
    assert gate.launches==0


@pytest.mark.parametrize('field',('receipt','transaction','pc'))
def test_full_original_input_is_checked_before_preparing_any_driver_work(field):
    ledger,gate,old=setup()
    tx=transaction();receipt=deepcopy(META)
    if field=='receipt':receipt['unused_predictor']['bit']=0
    elif field=='transaction':tx.resolve_meta['unused_predictor']['bit']=0
    else:tx=replace(tx,pc=PC+2)
    with pytest.raises(LifetimeError,match='changed before launch') as error:
        gate.prepare(old,tx,receipt_metadata=receipt)
    assert error.value.source is old and error.value.expected!=error.value.actual
    assert gate.pending is None and ledger.cached is None and gate.launches==0


def test_complete_metadata_is_frozen_at_original_publication_not_from_current_receipt():
    ledger=WindowLifetimes(2);gate=FeedbackGate(ledger)
    old=ledger.admit(PC,metadata=PROJECTION)
    supplied=deepcopy(META);gate.remember(old,supplied)
    supplied['unused_predictor']['bit']=0
    accept(gate,prepare(gate,old))
    assert gate.accepts==1


@pytest.mark.parametrize('field',('wide','unused','history'))
def test_mutation_after_preparation_is_rejected_at_the_driver_admission_boundary(field):
    _,gate,old=setup();tx=prepare(gate,old)
    if field=='wide':tx.resolve_meta['full_wide_field']^=1<<65
    elif field=='unused':tx.resolve_meta['unused_predictor']['bit']^=1
    else:tx.resolve_meta['phr']['phrLowBits']^=1
    with pytest.raises(LifetimeError,match='payload changed before driver'):gate.admit(tx)
    assert gate.launches==0


def test_an_equal_transaction_clone_cannot_take_the_prepared_driver_identity():
    _,gate,old=setup();tx=prepare(gate,old)
    with pytest.raises(LifetimeError,match='exact prepared'):gate.admit(replace(tx))
    assert gate.launches==0


@pytest.mark.parametrize('field',('metadata','start0','start2','target','position','padding-valid','padding-data','kind','action','taken','mispredict'))
def test_actual_acceptance_compares_complete_metadata_all_PC_copies_and_all_branch_slots(field):
    _,gate,old=setup();tx=prepare(gate,old);gate.admit(tx)
    actual=deepcopy(wire_payload(tx))
    if field=='metadata':actual['meta']['unused_predictor']['bit']^=1
    elif field=='start0':actual['start_pcs'][0][0]['addr']+=1
    elif field=='start2':actual['start_pcs'][2][1]['addr']+=8
    elif field=='padding-valid':actual['branches'][7]['valid']=1
    elif field=='padding-data':actual['branches'][7]['bits']['target_addr']=2
    else:
        bits=actual['branches'][0]['bits']
        if field=='kind':bits['attribute']['branchType']=2
        elif field=='action':bits['attribute']['rasAction']=1
        else:bits[{'target':'target_addr','position':'cfiPosition'}.get(field,field)]^=1
    with pytest.raises(LifetimeError,match='original payload changed'):gate.accept(actual,projection=PROJECTION)
    assert gate.accepts==0 and gate.pending is not None


def test_the_same_input_cannot_launch_twice_accept_twice_or_accept_before_launch():
    _,gate,old=setup();tx=prepare(gate,old)
    with pytest.raises(LifetimeError,match='no launched'):gate.accept(wire_payload(tx),projection=PROJECTION)
    gate.admit(tx)
    with pytest.raises(LifetimeError,match='already launched'):gate.admit(tx)
    gate.accept(wire_payload(tx),projection=PROJECTION)
    with pytest.raises(LifetimeError,match='no launched'):gate.accept(wire_payload(tx),projection=PROJECTION)


def test_single_cache_rejects_overwrite_and_launched_input_cannot_be_silently_cancelled():
    ledger,gate,old=setup();young=source(ledger,gate);tx=prepare(gate,old)
    with pytest.raises(LifetimeError,match='cache still occupied'):prepare(gate,young)
    gate.admit(tx)
    with pytest.raises(LifetimeError,match='already launched'):gate.cancel_unlaunched()
    assert gate.pending.source is old


def test_complete_original_publication_is_required_and_cannot_be_replaced():
    ledger=WindowLifetimes(2);gate=FeedbackGate(ledger)
    old=ledger.admit(PC,metadata=PROJECTION)
    with pytest.raises(LifetimeError,match='complete original metadata not published'):prepare(gate,old)
    gate.remember(old,META)
    with pytest.raises(LifetimeError,match='already published'):gate.remember(old,{'new':1})


@pytest.mark.parametrize('bad',((),(None,),tuple(None for _ in range(9)),(object(),)))
def test_invalid_branch_batches_are_rejected_without_prepared_or_driver_work(bad):
    _,gate,old=setup()
    with pytest.raises((ValueError,TypeError)):prepare(gate,old,replace(transaction(),branches=bad))
    assert gate.pending is None and gate.launches==0


def test_transport_projection_does_not_truncate_wide_original_metadata():
    _,gate,old=setup();tx=prepare(gate,old);accept(gate,tx)
    assert gate.originals[old.sequence]==freeze(META)
