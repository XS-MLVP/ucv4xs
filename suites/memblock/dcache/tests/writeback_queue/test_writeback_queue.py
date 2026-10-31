"""WritebackQueue UT: request, C-channel release, D ack, miss blocking."""
from __future__ import annotations

import pytest

from suites.memblock.dcache.execution import refresh

from suites.memblock.dcache.writeback_queue.coverage import WritebackQueueCoverage
from suites.memblock.dcache.writeback_queue.env import WbqEnv


@pytest.fixture
def wbq(dut_factory):
    dut = dut_factory("writeback_queue")
    return WbqEnv(dut, WritebackQueueCoverage())


# WQ-FP-001, WQ-FP-002
def test_release_data_and_ack(wbq):
    wbq.reset()
    addr = 0x8000
    pattern = int.from_bytes(bytes([0xA5] * 64), "little")
    info, chosen = wbq.issue_and_wait(addr, pattern, has_data=True, param=0)
    assert info["opcode"] == 7, info
    assert info["address"] == addr
    assert info["corrupt"] == 0
    assert info["data"] == (pattern & ((1 << 256) - 1)), hex(info["data"])
    wbq.ack(chosen, info["source"])
    wbq.drain(2)
    assert wbq.value(wbq.req["ready"]) == 1, "entry must be free after ReleaseAck"
    if wbq.coverage is not None:
        wbq.coverage.sample_ack(True)


# WQ-FP-002
def test_release_without_data(wbq):
    wbq.reset()
    info, chosen = wbq.issue_and_wait(0x9000, 0, has_data=False, param=0,
                                      voluntary=True)
    if wbq.coverage is not None:
        wbq.coverage.sample_ack(False)
    assert info["opcode"] == 6, info
    assert info["param"] == 0
    wbq.ack(chosen, info["source"])
    wbq.drain(2)
    assert wbq.value(wbq.req["ready"]) == 1


# WQ-FP-002
def test_probe_ack_merge(wbq):
    wbq.reset()
    info, chosen = wbq.issue_and_wait(0x9800, 0, has_data=False, param=1,
                                      voluntary=False)
    assert info["opcode"] == 4, info
    wbq.ack(chosen, info["source"])
    wbq.drain(2)


# WQ-FP-003
def test_channel_selection_by_address_bit6(wbq):
    wbq.reset()
    for addr, expected in ((0x8000, 0), (0x8040, 1)):
        info, chosen = wbq.issue_and_wait(addr, 0, has_data=False)
        assert chosen == expected, (addr, chosen)
        assert info["address"] == addr
        wbq.ack(chosen, info["source"])
        wbq.drain(2)


# WQ-FP-005
def test_block_matching_miss_requests(wbq):
    wbq.reset()
    addr = 0xA000
    info, chosen = wbq.issue_and_wait(addr, 0, has_data=False)
    block = wbq.block_probe(addr)
    assert any(block), block
    if wbq.coverage is not None:
        wbq.coverage.sample_block(True)
    block = wbq.block_probe(addr + 0x1000)
    assert not any(block), block
    if wbq.coverage is not None:
        wbq.coverage.sample_block(False)
    wbq.ack(chosen, info["source"])
    wbq.drain(2)


# WQ-FP-002
def test_probe_ack_data_merge(wbq):
    # A non-voluntary probe that asks for data must produce ProbeAckData (5),
    # not a plain ProbeAck, and keep the full line on the C channel.
    wbq.reset()
    line = int.from_bytes(bytes([0x3C] * 64), "little")
    info, chosen = wbq.issue_and_wait(0x9840, line, has_data=True, param=1,
                                      voluntary=False)
    assert info["opcode"] == 5, info
    assert info["address"] == 0x9840
    assert info["corrupt"] == 0
    wbq.ack(chosen, info["source"])
    wbq.drain(2)


# WQ-FP-004 / WQ-FP-005
def test_all_sixteen_entries_occupied(wbq):
    # Fill every release entry without acknowledging D; the 17th request must
    # be refused and the last entry (index 15) must have emitted its C beat.
    wbq.reset()
    issued = []
    for index in range(18):
        addr = 0x4000 + index * 0x40
        info, chosen = wbq.issue_and_wait(addr, index,
                                          has_data=(index % 2 == 0),
                                          param=0, voluntary=True)
        assert info["address"] == addr, (index, info)
        assert info["opcode"] == (7 if index % 2 == 0 else 6), (index, info)
        issued.append((addr, info, chosen))
    assert wbq.value(wbq.req["ready"]) == 0
    wbq.drive(0x4800, 0x55)
    refresh(wbq)
    assert wbq.value(wbq.req["ready"]) == 0
    wbq.req["valid"].Set(0)
    # Acknowledge the last entry so the queue can make progress again.
    addr, info, chosen = issued[-1]
    wbq.ack(chosen, info["source"])
    wbq.drain(4)


# WQ-FP-002 / WQ-FP-003
def test_release_opcode_is_independent_of_param(wbq):
    # opcode = {1'b1, voluntary, hasData}; param is a separate shrink/report
    # permission and must not change the opcode.
    wbq.reset()
    for param in (0, 1, 2, 3):
        info, chosen = wbq.issue_and_wait(0x9800 + param * 0x40, 0,
                                          has_data=False, param=param,
                                          voluntary=True)
        assert info["opcode"] == 6, (param, info)
        assert info["param"] == param
        wbq.ack(chosen, info["source"])
        wbq.drain(2)
    # ProbeAck (voluntary=0, hasData=0) keeps param too.
    info, chosen = wbq.issue_and_wait(0x9900, 0, has_data=False, param=2,
                                      voluntary=False)
    assert info["opcode"] == 4 and info["param"] == 2, info
    wbq.ack(chosen, info["source"])
    wbq.drain(2)
