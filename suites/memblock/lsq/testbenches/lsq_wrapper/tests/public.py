"""Typed expectation constructors for the composed LSQ wrapper tests.

They only build immutable transaction snapshots; no physical pin names appear
here.  Checks keep the original scenario's observation window and data-mask
policy.
"""
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import BypassResponse
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import CacheRequest
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import DeqCredit
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import ExceptionInfo
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import ForwardResponse
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import MdpTrain
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import NukeQuery
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Observation
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import ReplaySlot
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Rollback
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import SbufferWord
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import UncacheRequest
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Writeback
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr


def obs(**fields):
    return Observation(**fields)


def sq(position):
    return SqPtr.encode(position)


def lq(position):
    return QueuePtr.encode(position)


def perf(**values):
    base = [None] * 39
    for index, value in values.items():
        base[int(index.removeprefix("p"))] = value
    return tuple(base)


def dequeue(*, valid=None, count=None):
    return DeqCredit(valid, count)


def word(*, addr=None, vaddr=None, mask=None, data=None, wline=None, valid=None):
    return SbufferWord(valid, addr, vaddr, mask, data, wline)


def absent_word():
    return None


def lane_bypass(lane, **fields):
    entries = [None] * 3
    entries[lane] = BypassResponse(**fields)
    return tuple(entries)


def lane_forward(lane, **fields):
    entries = [None] * 3
    entries[lane] = ForwardResponse(**fields)
    return tuple(entries)


def lane_replay(bank, **fields):
    entries = [None] * 3
    entries[bank] = ReplaySlot(**fields)
    return tuple(entries)


def replays_absent():
    return (ReplaySlot(valid=0), ReplaySlot(valid=0), ReplaySlot(valid=0))


def rollback(**fields):
    return Rollback(**fields)


def mdp(**fields):
    return MdpTrain(**fields)


def uncache(**fields):
    return UncacheRequest(**fields)


def cbo(**fields):
    return CacheRequest(**fields)


def writeback(**fields):
    return Writeback(**fields)


def exception(**fields):
    return ExceptionInfo(**fields)


def nuke(**fields):
    return NukeQuery(**fields)


def all_nuke(lanes, **fields):
    entries = [None] * 3
    for lane in lanes:
        entries[lane] = NukeQuery(**fields)
    return tuple(entries)


def check_byte(response, expected):
    """Original one-byte Forward S2 window with the real query address."""
    va, pa, value = expected
    assert va % 4096 == pa % 4096
    offset = va % 16
    assert response.valid == 1, (va, "missing S2")
    assert not any((response.forward_invalid, response.match_invalid,
                    response.addr_invalid, response.data_invalid)), (va, "blocked")
    assert response.forward_mask == 1 << offset, (va, hex(response.forward_mask), "mask")
    assert (response.forward_data >> (8 * offset)) & 0xFF == value, (va, "payload")


def check_first_word(response, value):
    """Original cross-page first four bytes (offset 12..15)."""
    assert response.valid == 1
    assert not any((response.forward_invalid, response.match_invalid,
                    response.addr_invalid, response.data_invalid))
    assert response.forward_mask == 0xF000
    assert response.forward_data >> 96 == value & 0xFFFFFFFF


def check_sbuffer(env, lane, *, va, pa, mask, data, wline=0, before=False):
    """Original Sbuffer payload, with the byte lanes the Store actually owns."""
    data_mask = sum(0xFF << (8 * byte) for byte in range(16) if mask >> byte & 1)
    env.expect_sbuffer_word(lane, word(addr=pa, vaddr=va, mask=mask, data=data, wline=wline),
                            "original Store bytes actually consumed by Sbuffer",
                            data_mask=data_mask, before=before)
