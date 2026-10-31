"""SplitCtrl semantic model qualification without DUT coverage credit."""
import pytest

from suites.vector.vagq.split.model import State, element, idx_offset, need_flush, pending
from suites.vector.vagq.split.types import Beat, Entry, Redirect

pytestmark = pytest.mark.toffee_functional_coverage(False)


def entry(**changes):
    values = dict(valid=True, state=3, elem_valid=0xffff, elem_active=0x000f,
                  req_sent=0, req_ack=0, ordered_can_proceed=True,
                  rob_value=10, base_addr=0x1000, op2_data=4)
    values.update(changes)
    return Entry(**values)


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def beat(entries, **kwargs):
    values = list(Entry() for _ in range(8))
    for index, value in entries.items():
        values[index] = value
    return Beat(entries=tuple(values), older_matrix=matrix(), **kwargs)


def test_pending_masks_separate_active_empty_and_ordered_blocking():
    active, empty = pending(beat({0: entry(elem_valid=0x0f, elem_active=0x05)}))
    assert active[0] == 0x05 and empty[0] == 0x0a

    active, empty = pending(beat({0: entry(req_sent=0x01, req_ack=0x00)}))
    assert active[0] == 0x0e and empty[0] == 0xfff0

    active, empty = pending(beat({0: entry(uop_type=6, req_sent=0x01, elem_active=0x03)}))
    assert active[0] == 0 and empty[0] == 0xfffc


def test_oldest_selection_is_independent_for_active_and_empty():
    entries = {
        0: entry(elem_valid=0x01, elem_active=0x01, rob_value=20),
        1: entry(elem_valid=0x02, elem_active=0x00, rob_value=10),
    }
    state = State()
    observed = state.observe(beat(entries))
    assert observed.update[0].entry_oh == 0x01
    assert observed.update[1].entry_oh == 0x02


def test_ordered_load_uses_one_active_lane_and_normal_load_partitions_three_lanes():
    normal = State().following(beat({0: entry(elem_active=0b111, uop_type=0)})).observe(beat({}))
    assert [req.byte_offset if req else None for req in normal.lsu] == [0, 1, 2]

    ordered = State().following(beat({0: entry(elem_active=0b111, uop_type=6)})).observe(beat({}))
    assert ordered.lsu[0] is not None and ordered.lsu[1] is None and ordered.lsu[2] is None


def test_stage_holds_under_backpressure_then_fires_and_cancels_faulting_lane():
    state = State()
    first = beat({0: entry(elem_active=0x07)}, lsu_ready=(False, False, False))
    state = state.following(first)
    held = state.observe(beat({}, lsu_ready=(False, False, False)))
    assert all(request is not None for request in held.lsu)
    state = state.following(beat({}, lsu_ready=(True, True, True)))
    assert all(request is None for request in state.observe(beat({})).lsu)

    fault_state = State().following(beat({0: entry(elem_active=0x03, exception=True, fault_elem=0)}))
    observed = fault_state.observe(beat({}))
    assert observed.lsu[0] is not None and observed.lsu[1] is None
    assert observed.excp.valid and observed.excp.excp_set == 0x02


def test_redirect_flush_suppresses_staged_requests_and_pending_entry():
    state = State().following(beat({0: entry(elem_active=0x01)}))
    redirect = Redirect(True, 1, 0, 10)
    observed = state.observe(beat({}, redirect=redirect))
    assert observed.lsu == (None, None, None)
    assert observed.empty == (None, None)


def test_redirect_uses_circular_rob_order_and_flush_itself_level():
    # RobPtr.isAfter is flag-XOR-value-GT, not a lexicographic tuple compare.
    assert need_flush(1, 2, Redirect(True, 0, 0, 100))
    assert not need_flush(1, 100, Redirect(True, 0, 0, 2))
    assert need_flush(0, 17, Redirect(True, 1, 0, 17))


def test_wide_first_mop_at_byte_eight_is_still_element_base():
    value = entry(nf=4, deew=2, ieew=3, elem_base=2, start_byte=8, start_field=0)
    assert idx_offset(8, value) == 0  # old site.orR produced 1
    assert element(8, value).idx_offset == 0


def test_stream_position_handles_continuation_then_the_next_element():
    # Five e32 fields: a continuation of field 4 starts at byte 0, then
    # the next element begins at byte 4. No generated lookup is needed.
    value = entry(nf=4, deew=2, ieew=2, start_field=4, start_byte=0)
    assert idx_offset(0, value) == 0
    assert idx_offset(4, value) == 1
    # Five e64 fields, field 2 continuation: 24 bytes remain, so this
    # 16-byte request must be full, never a zero-width memory operation.
    wide = entry(nf=4, deew=3, ieew=3, start_field=2, start_byte=0)
    assert element(0, wide).data_mask == 0xFFFF


def test_selected_site_cannot_precede_the_declared_first_mop():
    with pytest.raises(ValueError, match='contradicts'):
        idx_offset(0, entry(nf=1, start_field=1, start_byte=1))
