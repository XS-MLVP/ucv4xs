"""Input identity and phase witnesses, independent of returned predictor data."""
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.mbtb.checker.lookup_inputs import LookupInputs
from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup
from suites.frontend.bpu.mbtb.model.semantic import Events

PC = 0x80000000


def plan():
    inputs = LookupInputs()
    for uid in (10, 12):
        inputs.plan(uid, MbtbLookup(PC))
    return inputs


def first(inputs):
    inputs.launched(10, 2)
    inputs.observe(2, Events(select=True, pc=PC))
    inputs.stage(10, 'advance')
    inputs.stage_launched(10, 'advance', 4)
    inputs.observe(4, Events(advance=True))
    inputs.observe_output(6)
    inputs.delivered(10,6)
    inputs.stage(10, 'consume')
    inputs.stage_launched(10, 'consume', 6)
    inputs.observe(6, Events(consume=True))


def test_equal_payloads_retain_distinct_input_and_stage_identities():
    inputs = plan()
    first(inputs)
    inputs.launched(12, 8)
    inputs.observe(8, Events(select=True, pc=PC))
    inputs.stage(12, 'advance')
    inputs.stage_launched(12, 'advance', 10)
    inputs.observe(10, Events(advance=True))
    inputs.observe_output(12)
    inputs.delivered(12,12)
    inputs.stage(12, 'consume')
    inputs.stage_launched(12, 'consume', 12)
    inputs.observe(12, Events(consume=True))
    assert [row.uid for row in inputs.finish()] == [10, 12]
    assert [row['state'] for row in inputs.receipt()] == ['responded'] * 2


def test_a_wrong_wire_pc_cannot_be_waived_by_a_custom_response_expected():
    inputs = plan()
    inputs.launched(10, 2)
    with pytest.raises(ScoreboardMismatch) as caught:
        inputs.observe(2, Events(select=True, pc=PC ^ 0x80))
    with pytest.raises(ScoreboardMismatch) as later:
        inputs.finish()
    assert later.value is caught.value


def test_a_correct_stale_payload_is_not_a_new_response_without_the_named_s1():
    inputs = plan()
    first(inputs)
    inputs.launched(12, 8)
    inputs.observe(8, Events(select=True, pc=PC))
    inputs.stage(12, 'advance')
    inputs.observe(10, Events())
    with pytest.raises(ScoreboardMismatch) as caught:
        inputs.observe_output(12)
    assert caught.value.context.sequence_id == 12


@pytest.mark.parametrize('stage', ('select', 'advance', 'consume', 'last_stage'))
def test_an_unplanned_physical_stage_cannot_infer_an_id_from_old_payload(stage):
    inputs = LookupInputs()
    with pytest.raises(ScoreboardMismatch):
        inputs.observe(2, Events(**{stage: True}))


def test_s2_is_owned_by_the_original_frame_even_when_the_pc_is_identical():
    inputs = plan()
    first(inputs)
    inputs.launched(12, 8)
    inputs.observe(8, Events(select=True, pc=PC))
    inputs.stage(12, 'consume')
    with pytest.raises(ScoreboardMismatch):
        inputs.observe(10, Events(consume=True))


def test_pending_cancel_preserves_its_named_uid_without_fabricating_a_response():
    inputs = LookupInputs()
    inputs.plan(1, MbtbLookup(PC))
    inputs.cancel_pending(1, 0)
    inputs.observe(2, Events())
    row, = inputs.finish()
    assert row.uid == 1 and row.state == 'cancelled-before-offer'
    assert row.offer_tick is row.response_tick is None


@pytest.mark.parametrize('fault', ('early-offer', 'late-offer', 'later-sdk-notification'))
def test_actual_offer_and_sdk_launch_need_exact_time_not_just_equal_pc(fault):
    inputs = LookupInputs()
    inputs.plan(1, MbtbLookup(PC))
    if fault != 'later-sdk-notification':
        inputs.launched(1, 4 if fault == 'early-offer' else 0)
        with pytest.raises(ScoreboardMismatch):
            inputs.observe(2, Events(select=True, pc=PC))
    else:
        inputs.observe(2, Events(select=True, pc=PC))
        inputs.launched(1, 4)
        with pytest.raises(ScoreboardMismatch):
            inputs.finish()


def test_reset_epoch_removes_the_old_read_and_frame_owner():
    inputs = plan()
    inputs.launched(10, 2)
    inputs.observe(2, Events(select=True, pc=PC))
    inputs.observe(4, Events(reset=True))
    assert inputs.epoch == 1 and inputs.rows[0].state == 'reset-cancelled'
    inputs.launched(12, 6)
    inputs.observe(6, Events(select=True, pc=PC))
    inputs.stage(10, 'advance')
    inputs.observe(8, Events(advance=True))
    assert inputs.frame_uid is None


def test_deferred_s2_is_explicitly_not_offered_and_needs_its_scope_to_exit():
    inputs = LookupInputs()
    inputs.plan(10, MbtbLookup(PC))
    inputs.launched(10, 2)
    inputs.observe(2, Events(select=True, pc=PC))
    inputs.stage(10, 'advance')
    inputs.stage_launched(10, 'advance', 4)
    inputs.observe(4, Events(advance=True))
    inputs.observe_output(6)
    inputs.delivered(10,6)
    with pytest.raises(AssertionError, match='explicit cleanup scope'):
        inputs.defer_consume(10)
    inputs.open_cleanup_scope()
    inputs.defer_consume(10)
    with pytest.raises(ScoreboardMismatch):
        inputs.finish()
    inputs.close_cleanup_scope()
    inputs.finish()
    assert inputs.receipt()[0]['consume_disposition'] == 'not-offered-in-explicit-scope'


def test_repeated_retained_s2_keeps_the_named_original_not_a_new_lookup():
    inputs = LookupInputs()
    inputs.plan(10, MbtbLookup(PC))
    inputs.launched(10, 2)
    inputs.observe(2, Events(select=True, pc=PC))
    inputs.stage(10, 'advance')
    inputs.stage_launched(10, 'advance', 4)
    inputs.observe(4, Events(advance=True))
    inputs.observe_output(6)
    inputs.delivered(10,6)
    inputs.open_cleanup_scope()
    inputs.defer_consume(10)
    inputs.observe(6, Events(consume=True))
    inputs.observe(8, Events(consume=True))
    inputs.close_cleanup_scope()
    assert inputs._retained_consumes == [(1, 6, 10), (1, 8, 10)]
    assert len(inputs.finish()) == 1


def test_input_only_queries_have_no_fake_sdk_response_handle_but_still_need_a_result_or_reset():
    inputs = LookupInputs()
    inputs.plan(10, MbtbLookup(PC), input_only=True)
    inputs.launched(10, 2)
    inputs.observe(2, Events(select=True, pc=PC))
    inputs.stage(10, 'advance')
    inputs.stage_launched(10, 'advance', 6)
    inputs.observe(6, Events(advance=True))
    inputs.observe_output(8)
    inputs.stage(10, 'consume')
    inputs.stage_launched(10, 'consume', 8)
    inputs.observe(8, Events(consume=True))
    assert inputs.finish()[0].response_tick == 8
