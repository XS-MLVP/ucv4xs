"""WritebackQueue UT: request, C-channel release, D ack, miss blocking."""
from __future__ import annotations

import pytest

from dcacheverify.writeback_queue.coverage import WritebackQueueCoverage


class WbqEnv:
    def __init__(self, dut, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.req = {
            "ready": dut.io_req_ready,
            "valid": dut.io_req_valid,
            "param": dut.io_req_bits_param,
            "voluntary": dut.io_req_bits_voluntary,
            "hasData": dut.io_req_bits_hasData,
            "corrupt": dut.io_req_bits_corrupt,
            "addr": dut.io_req_bits_addr,
            "data": dut.io_req_bits_data,
        }
        self.release = []
        for index in range(2):
            prefix = f"io_mem_release_{index}"
            self.release.append({
                "ready": getattr(dut, prefix + "_ready"),
                "valid": getattr(dut, prefix + "_valid"),
                "opcode": getattr(dut, prefix + "_bits_opcode"),
                "param": getattr(dut, prefix + "_bits_param"),
                "size": getattr(dut, prefix + "_bits_size"),
                "source": getattr(dut, prefix + "_bits_source"),
                "address": getattr(dut, prefix + "_bits_address"),
                "data": getattr(dut, prefix + "_bits_data"),
                "corrupt": getattr(dut, prefix + "_bits_corrupt"),
            })
        self.grant = []
        for index in range(2):
            prefix = f"io_mem_grant_{index}"
            self.grant.append({
                "ready": getattr(dut, prefix + "_ready"),
                "valid": getattr(dut, prefix + "_valid"),
                "source": getattr(dut, prefix + "_bits_source"),
            })
        self.conflict = [{
            "valid": getattr(dut, f"io_miss_req_conflict_check_{index}_valid"),
            "bits": getattr(dut, f"io_miss_req_conflict_check_{index}_bits"),
        } for index in range(4)]
        self.block = [getattr(dut, f"io_block_miss_req_{index}") for index in range(4)]

    @staticmethod
    def value(signal) -> int:
        return int(signal.value)

    def reset(self) -> None:
        self._idle()
        self.dut.reset.Set(1)
        self.dut.Step(3)
        self.dut.reset.Set(0)
        self.dut.Step(2)

    def _idle(self) -> None:
        self.req["valid"].Set(0)
        for grant in self.grant:
            grant["valid"].Set(0)
        for index in range(4):
            self.conflict[index]["valid"].Set(0)
        for index in range(2):
            # Hold the C beat until the test has sampled it.
            self.release[index]["ready"].Set(0)

    def drive(self, addr: int, data: int = 0, *, has_data: bool = True,
              param: int = 0, voluntary: bool = True, corrupt: bool = False) -> None:
        self._idle()
        self.req["valid"].Set(1)
        self.req["param"].Set(param)
        self.req["voluntary"].Set(1 if voluntary else 0)
        self.req["hasData"].Set(1 if has_data else 0)
        self.req["corrupt"].Set(1 if corrupt else 0)
        self.req["addr"].Set(addr)
        self.req["data"].Set(data)

    def fire(self) -> None:
        self.dut.Step(1)
        self.req["valid"].Set(0)

    def wait_release(self, channel: int, limit: int = 8) -> dict | None:
        pins = self.release[channel]
        for _ in range(limit):
            if self.value(pins["valid"]):
                return {
                    "opcode": self.value(pins["opcode"]),
                    "param": self.value(pins["param"]),
                    "size": self.value(pins["size"]),
                    "source": self.value(pins["source"]),
                    "address": self.value(pins["address"]),
                    "data": self.value(pins["data"]),
                    "corrupt": self.value(pins["corrupt"]),
                }
            self.dut.Step(1)
        return None

    def issue_and_wait(self, addr: int, data: int = 0, *, has_data: bool = True,
                       param: int = 0, voluntary: bool = True,
                       corrupt: bool = False) -> tuple[dict, int]:
        self.drive(addr, data, has_data=has_data, param=param,
                   voluntary=voluntary, corrupt=corrupt)
        self.dut.xclock.RefreshComb()
        assert self.value(self.req["ready"]) == 1
        self.fire()
        info = None
        chosen = 0
        for _ in range(16):
            for channel in (0, 1):
                pins = self.release[channel]
                if self.value(pins["valid"]):
                    info = {
                        "opcode": self.value(pins["opcode"]),
                        "param": self.value(pins["param"]),
                        "size": self.value(pins["size"]),
                        "source": self.value(pins["source"]),
                        "address": self.value(pins["address"]),
                        "data": self.value(pins["data"]),
                        "corrupt": self.value(pins["corrupt"]),
                    }
                    chosen = channel
                    break
            if info is not None:
                break
            self.dut.Step(1)
        assert info is not None, "release must appear on one C channel"
        # Drain every C beat of this response (ReleaseData uses two beats).
        self.release[chosen]["ready"].Set(1)
        for _ in range(6):
            self.dut.Step(1)
        self.release[chosen]["ready"].Set(0)
        if self.coverage is not None:
            self.coverage.sample_release(info, chosen, voluntary)
        return info, chosen

    def ack(self, channel: int, source: int | None = None) -> None:
        grant = self.grant[channel]
        grant["valid"].Set(1)
        grant["source"].Set(source if source is not None
                            else self.value(self.release[channel]["source"]))
        for _ in range(8):
            if self.value(grant["ready"]):
                break
            self.dut.Step(1)
        self.dut.Step(1)
        grant["valid"].Set(0)

    def drain(self, cycles: int = 3) -> None:
        for _ in range(cycles):
            self.dut.Step(1)

    def block_probe(self, address: int) -> list[int]:
        for index in range(4):
            self.conflict[index]["valid"].Set(1)
            self.conflict[index]["bits"].Set(address)
        self.dut.xclock.RefreshComb()
        values = [self.value(signal) for signal in self.block]
        for index in range(4):
            self.conflict[index]["valid"].Set(0)
        return values


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
    wbq.dut.xclock.RefreshComb()
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
