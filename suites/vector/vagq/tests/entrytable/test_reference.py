"""EntryTable model qualification uses semantic packets, not DUT outputs."""
import pytest

from vagqverify.entrytable.model import SPLIT, WAIT_A, WAIT_SI, State
from vagqverify.entrytable.types import AddrPacket, Beat, DataPacket, Redirect, SplitReq

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_address_then_data_completes_a_split_entry():
    addr = AddrPacket(entry_idx=0, rob_value=10, vl=1)
    data = DataPacket(entry_idx=0, rob_value=10, op2_data=0x1234)
    state = State()
    after_addr = state.following(Beat(addr=(addr, None), addr_valid=(True, False)))
    assert after_addr.entries[0].valid and after_addr.entries[0].state == WAIT_SI
    after_data = after_addr.following(Beat(data=(data, None), data_valid=(True, False)))
    assert after_data.entries[0].state == SPLIT
    assert after_data.entries[0].op2_data == 0x1234


def test_same_cycle_address_and_data_enters_split_with_mask_initialized():
    addr = AddrPacket(entry_idx=2, rob_value=11, vl=1)
    data = DataPacket(entry_idx=2, rob_value=11, op2_data=7)
    result = State().following(Beat(addr=(addr, None), addr_valid=(True, False),
                                    data=(data, None), data_valid=(True, False)))
    entry = result.entries[2]
    assert entry.state == SPLIT and entry.valid
    assert entry.req_sent == 0 and entry.req_ack == 0 and entry.data_sent == 0


def test_bitmap_store_exception_and_flush_updates_are_independent():
    addr = AddrPacket(entry_idx=0, rob_value=10, vl=1)
    data = DataPacket(entry_idx=0, rob_value=10, op2_data=1)
    state = State().following(Beat(addr=(addr, None), addr_valid=(True, False),
                                   data=(data, None), data_valid=(True, False)))
    state = state.following(Beat(
        split_req=(SplitReq(True, 1, 1), SplitReq()),
    ))
    assert state.entries[0].req_sent & 1
    flushed = state.following(Beat(redirect=Redirect(True, 1, 0, 10)))
    assert not flushed.entries[0].valid


def test_data_only_initializes_waitA_and_redirect_uses_rob_age():
    data = DataPacket(entry_idx=3, rob_value=20, op2_data=9)
    state = State().following(Beat(index=(data, None), index_valid=(True, False)))
    assert state.entries[3].valid and state.entries[3].state == WAIT_A
    result = state.following(Beat(redirect=Redirect(True, 0, 0, 10)))
    assert not result.entries[3].valid
