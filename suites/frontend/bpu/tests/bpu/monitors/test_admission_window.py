"""Owned acceptance-window controls; no SDK or DUT observations are golden."""
from types import SimpleNamespace as N
import pytest
from bpuverify.bpu.monitor.admission_window import AdmissionWindow

PC=0x40000800


def row(**changes):return dict(dict(reset=0,fire=1,flush=0,pc=PC),**changes)


def cycle(sequence=1,*,fire=True,flush=False,pc=PC):
    return N(tokens=(N(pc=pc,sequence=sequence),None,None),fires=(False,fire,False,False),flushes=(flush,False,False))


async def test_candidate_is_not_acceptance_and_only_the_exact_following_checked_event_completes():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    pre,event=N(tick=10),N(tick=11)
    selector.candidate(pre,row())
    assert window.prepared.result() is pre and not window.accepted.done()
    selector.capture(event,cycle())
    assert selector.finish(window,event)==((11,1),)


async def test_quota_two_closes_on_second_actual_occurrence_not_second_candidate_poll():
    selector=AdmissionWindow();window=selector.arm(PC,2,available=2)
    selector.candidate(N(tick=10),row());selector.candidate(N(tick=10),row())
    assert not window.prepared.done()
    selector.capture(N(tick=11),cycle(1))
    selector.candidate(N(tick=12),row())
    final=N(tick=13);selector.capture(final,cycle(2))
    assert selector.finish(window,final)==((11,1),(13,2))


@pytest.mark.parametrize('change',({'reset':1},{'fire':0},{'flush':1},{'pc':PC+2}))
async def test_reset_stall_flush_or_wrong_PC_cannot_prepare_closure(change):
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    selector.candidate(N(tick=10),dict(row(),**change))
    assert not window.prepared.done() and not window.accepted.done()
    selector.cancel(window)


@pytest.mark.parametrize('delta',(0,2,3))
async def test_stale_or_wrong_phase_distance_cannot_substitute_for_actual_acceptance(delta):
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    selector.candidate(N(tick=10),row())
    with pytest.raises(AssertionError,match='exact pre-edge'):selector.capture(N(tick=10+delta),cycle())
    assert not window.accepted.done();selector.cancel(window)


async def test_unprepared_actual_admission_is_an_error_not_a_synthetic_receipt():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    with pytest.raises(AssertionError,match='pre-edge'):selector.capture(N(tick=11),cycle())
    assert not window.accepted.done();selector.cancel(window)


@pytest.mark.parametrize('fire,flush',((False,False),(True,True)))
async def test_stalled_or_squashed_S1_does_not_consume_quota(fire,flush):
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    selector.capture(N(tick=11),cycle(fire=fire,flush=flush))
    assert not window.receipts and not window.accepted.done();selector.cancel(window)


async def test_an_unexpected_accepted_PC_is_not_filtered_out_of_a_bounded_window():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    with pytest.raises(AssertionError,match='unexpected PC'):selector.capture(N(tick=11),cycle(pc=PC+2))
    selector.cancel(window)


async def test_an_extra_real_admission_after_quota_is_not_hidden_by_completed_future():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    selector.candidate(N(tick=10),row());selector.capture(N(tick=11),cycle())
    with pytest.raises(AssertionError,match='beyond'):selector.capture(N(tick=13),cycle(2))
    selector.cancel(window)


async def test_finish_requires_the_identical_driver_event_not_an_equal_timestamp_clone():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    selector.candidate(N(tick=10),row());event=N(tick=11);selector.capture(event,cycle())
    with pytest.raises(AssertionError,match='exact accepting'):selector.finish(window,N(tick=11))
    selector.finish(window,event)


async def test_quota_is_rejected_before_arming_when_the_real_remaining_capacity_is_insufficient():
    selector=AdmissionWindow()
    with pytest.raises(ValueError,match='capacity'):selector.arm(PC,2,available=1)
    assert selector.current is None


@pytest.mark.parametrize('quota',(0,-1,True,1.5))
async def test_quota_is_a_positive_semantic_count_not_a_delay(quota):
    selector=AdmissionWindow()
    with pytest.raises(ValueError):selector.arm(PC,quota,available=8)
    assert selector.current is None


async def test_pending_window_cannot_be_replaced_and_cancel_is_explicit():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1)
    with pytest.raises(RuntimeError):selector.arm(PC,1,available=1)
    selector.cancel(window)
    assert window.prepared.cancelled() and window.accepted.cancelled()
    new=selector.arm(PC,1,available=1);selector.cancel(window)
    assert selector.current is new;selector.cancel(new)


async def test_prediction_mode_can_use_actual_acceptance_without_service_preparation():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1,requires_preparation=False)
    event=N(tick=11);selector.capture(event,cycle())
    assert not window.prepared.done() and selector.finish(window,event)==((11,1),)


async def test_actual_only_mode_still_rejects_extra_acceptance():
    selector=AdmissionWindow();window=selector.arm(PC,1,available=1,requires_preparation=False)
    selector.capture(N(tick=11),cycle())
    with pytest.raises(AssertionError,match='beyond'):selector.capture(N(tick=13),cycle(2))
    selector.cancel(window)
