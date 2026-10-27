"""MergeCtrl semantic model qualification without DUT coverage credit."""
import pytest

from vagqverify.merge.model import State, _expand_mask
from vagqverify.merge.types import Beat, Entry, Redirect, Response

pytestmark = pytest.mark.toffee_functional_coverage(False)


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def entry(index=0, **changes):
    values = dict(
        valid=True,
        uop_type=0,
        rob_value=32 + index,
        pdest=40 + index,
        psrc2=50 + index,
        uop_idx=index,
        merge_write=0xfffc,
        elem_agnostic=0,
        elem_active=0x0003,
        req_ack=0xffff,
        state=4,
        ordered_can_proceed=True,
    )
    values.update(changes)
    return Entry(**values)


def beat(entries=None, **changes):
    values = [Entry() for _ in range(8)]
    ready = [False] * 8
    for index, value in (entries or {}).items():
        values[index] = value
        ready[index] = True
    ready = changes.pop('psrc2_ready', tuple(ready))
    return Beat(entries=tuple(values), psrc2_ready=tuple(ready), older_matrix=matrix(), **changes)


def test_response_updates_distinguish_ack_nack_exception_and_stale_entry():
    state = State()
    observed = state.observe(beat(
        {0: entry()},
        ldu_resp=(Response(True, 0, 0x3), Response(), Response(True, 1, 0x4, is_nack=True),),
    ))
    assert observed.updates[0].entry_hit_oh == 1
    assert observed.updates[0].set_req_ack == 3
    assert observed.updates[2].entry_hit_oh == 0
    assert observed.updates[2].clear_req_sent == 4


def test_split_done_selects_load_merge_store_wb_and_skip_merge():
    load = entry(state=3, uop_type=0, merge_write=0xfffc, req_ack=0xffff)
    store = entry(1, state=3, uop_type=1, merge_write=0xfffc, req_ack=0xffff)
    observed = State().observe(beat({0: load, 1: store}))
    assert observed.split_done.valid and observed.split_done.entry_oh == 1
    assert observed.split_done.state_next == 4

    observed = State().observe(beat({0: entry(state=3, uop_type=0, skip_merge=True)}))
    assert observed.split_done.state_next == 5


def test_old_vd_read_response_merges_agnostic_bytes_and_completes_write():
    state = State()
    current = beat(
        {0: entry(merge_write=0x00ff, elem_agnostic=0x00f0)},
        psrc2_ready=(True,) + (False,) * 7,
    )
    assert state.observe(current).vrf_read.valid
    state = state.following(Beat(
        entries=current.entries,
        psrc2_ready=current.psrc2_ready,
        older_matrix=current.older_matrix,
        vrf_read_req_ready=True,
    ))
    response = Beat(
        entries=current.entries,
        psrc2_ready=current.psrc2_ready,
        older_matrix=current.older_matrix,
        vrf_read_resp_valid=True,
        vrf_read_resp_entry_idx=0,
        vrf_read_resp_rob_value=32,
        vrf_read_resp_data=0x1234,
    )
    state = state.following(response)
    observed = state.observe(response)
    assert observed.vrf_write.valid
    assert observed.vrf_write.mask == 0x00ff
    assert observed.vrf_write.data == (0x1234 | _expand_mask(0x00f0))
    assert observed.merge_done.valid


def test_no_old_vd_uses_zero_base_and_redirect_cancels_pending_read():
    no_read = beat({0: entry(merge_write=0, elem_agnostic=0)})
    state = State().following(no_read)
    assert state.merge_resp_valid
    assert state.observe(no_read).vrf_write.valid

    read = beat(
        {0: entry(merge_write=1, elem_agnostic=0)},
        psrc2_ready=(True,) + (False,) * 7,
    )
    state = State().following(Beat(
        entries=read.entries,
        psrc2_ready=read.psrc2_ready,
        older_matrix=read.older_matrix,
        vrf_read_req_ready=True,
    ))
    flushed = Beat(
        entries=read.entries,
        psrc2_ready=read.psrc2_ready,
        older_matrix=read.older_matrix,
        redirect=Redirect(True, 1, 0, 32),
    )
    assert not state.following(flushed).merge_read_valid
