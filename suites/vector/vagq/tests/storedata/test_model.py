"""StoreDataCtrl semantic model qualification without DUT coverage credit."""
import pytest

from vagqverify.storedata.model import State, _sq_add, _store_flow_data, need_flush
from vagqverify.storedata.types import Beat, Entry, Redirect, VrfReadResponse

pytestmark = pytest.mark.toffee_functional_coverage(False)


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def entry(index=0, **changes):
    values = dict(
        valid=True,
        uop_type=1,
        rob_value=32 + index,
        psrc2=16 + index,
        deew=0,
        start_byte=0,
        elem_active=0xffff,
        req_ack=1,
        data_sent=0,
        state=3,
        sq_value=3,
        ordered_can_proceed=True,
    )
    values.update(changes)
    return Entry(**values)


def beat(entries=None, **changes):
    values = [Entry() for _ in range(8)]
    for index, value in (entries or {}).items():
        values[index] = value
    return Beat(entries=tuple(values), older_matrix=matrix(), **changes)


def test_ack_and_candidate_gates_control_vrf_admission():
    no_ack = beat({0: entry(req_ack=0)})
    assert State().observe(no_ack).vrf_read_req.valid is False

    ready_blocked = beat({0: entry()}, psrc2_ready=(False,) + (True,) * 7)
    assert State().observe(ready_blocked).vrf_read_req.valid is False

    admitted = beat({0: entry()}, psrc2_ready=(True,) + (False,) * 7)
    request = State().observe(admitted).vrf_read_req
    assert request.valid and request.entry_idx == 0 and request.psrc2 == 16


def test_matching_response_establishes_slot_and_generates_low_pending_flow():
    initial = beat(
        {0: entry(elem_active=0x05, req_ack=0x05)},
        psrc2_ready=(True,) + (False,) * 7,
        vrf_read_req_ready=True,
    )
    state = State().following(initial)
    response = VrfReadResponse(True, 0, 0, 32, int.from_bytes(bytes(range(16)), 'little'))
    state = state.following(beat({0: entry(elem_active=0x05, req_ack=0x05)}, vrf_read_resp=response))
    observed = state.observe(beat({0: entry(elem_active=0x05, req_ack=0x05)}))
    assert observed.store_data[0] is not None
    assert observed.update[0].valid is False
    assert observed.store_data[0].data == _store_flow_data(response.data, 0, 0)


def test_eew_repetition_and_sq_start_offset_are_independent():
    data = int.from_bytes(bytes(range(16)), 'little')
    for deew in range(4):
        payload = _store_flow_data(data, 1, deew)
        width = 1 << deew
        elem = (data >> (width * 8)) & ((1 << (width * 8)) - 1)
        assert payload == sum(elem << (i * width * 8) for i in range(16 // width))
    assert _sq_add(0, 1, 63, 1) == (1, 0, 0)
    assert _sq_add(1, 1, 63, 1) == (0, 0, 0)


def test_stale_response_and_circular_redirect_do_not_resurrect_old_read():
    initial = beat(
        {0: entry()},
        psrc2_ready=(True,) + (False,) * 7,
        vrf_read_req_ready=True,
    )
    state = State().following(initial)
    stale = VrfReadResponse(True, 0, 0, 33, 0x1234)
    state = state.following(beat({0: entry(rob_value=33)}, vrf_read_resp=stale))
    assert state.read_pending is False
    assert not any(slot.valid for slot in state.slots)

    assert need_flush(1, 2, Redirect(True, 0, 0, 100))
    assert not need_flush(1, 100, Redirect(True, 0, 0, 2))
