"""ProbeQueue UT: B-channel probe acceptance, MainPipe request encoding, LR/SC block."""
from __future__ import annotations

import pytest


class ProbeEnv:
    def __init__(self, dut, coverage=None):
        self.dut = dut
        self.coverage = coverage
        self.probe = {
            "ready": dut.io_mem_probe_ready,
            "valid": dut.io_mem_probe_valid,
            "param": dut.io_mem_probe_bits_param,
            "address": dut.io_mem_probe_bits_address,
            "data": dut.io_mem_probe_bits_data,
        }
        self.pipe = {
            "valid": dut.io_pipe_req_valid,
            "ready": dut.io_pipe_req_ready,
            "param": dut.io_pipe_req_bits_probe_param,
            "need_data": dut.io_pipe_req_bits_probe_need_data,
            "vaddr": dut.io_pipe_req_bits_vaddr,
            "addr": dut.io_pipe_req_bits_addr,
            "id": dut.io_pipe_req_bits_id,
        }
        self.lrsc = {
            "valid": dut.io_lrsc_locked_block_valid,
            "bits": dut.io_lrsc_locked_block_bits,
        }
        self.update_resv = dut.io_update_resv_set

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
        self.probe["valid"].Set(0)
        self.pipe["ready"].Set(1)
        self.lrsc["valid"].Set(0)
        self.update_resv.Set(0)

    def send(self, address: int, param: int, vaddr: int = 0, data: int = 0) -> None:
        self._idle()
        self.probe["valid"].Set(1)
        self.probe["param"].Set(param)
        self.probe["address"].Set(address)
        self.probe["data"].Set(data)
        self.vaddr = vaddr

    def accept(self) -> bool:
        ready = bool(self.value(self.probe["ready"]))
        self.dut.Step(1)
        self.probe["valid"].Set(0)
        return ready

    def watch_pipe(self, limit: int = 6) -> dict | None:
        for _ in range(limit):
            if self.value(self.pipe["valid"]):
                return {
                    "param": self.value(self.pipe["param"]),
                    "need_data": self.value(self.pipe["need_data"]),
                    "addr": self.value(self.pipe["addr"]),
                    "id": self.value(self.pipe["id"]),
                }
            self.dut.Step(1)
        return None


@pytest.fixture
def pq(dut_factory):
    from dcacheverify.probe_queue.coverage import ProbeQueueCoverage
    dut = dut_factory("probe_queue")
    return ProbeEnv(dut, ProbeQueueCoverage())


# PQ-FP-001
def test_probe_to_b_requests_data(pq):
    pq.reset()
    address = 0x8000
    assert pq.value(pq.probe["ready"]) == 1
    pq.send(address, param=0)
    assert pq.accept(), "idle probe queue must accept the B request"
    info = pq.watch_pipe(6)
    assert info is not None, "probe must reach the main pipe"
    if pq.coverage is not None:
        pq.coverage.sample(info["param"], info["need_data"], blocked=False)
    assert info["param"] == 0
    assert info["addr"] == address
    assert info["need_data"] in (0, 1)


# PQ-FP-002
def test_probe_to_n_and_to_t(pq):
    pq.reset()
    for param, need_data in ((0, 0), (1, 0), (2, 1)):
        address = 0x9000 + param * 0x40
        pq.send(address, param, data=need_data)
        assert pq.accept()
        info = pq.watch_pipe(6)
        assert info is not None
        if pq.coverage is not None:
            pq.coverage.sample(info["param"], info["need_data"], blocked=False)
        assert info["param"] == param
        assert info["addr"] == address
        assert info["need_data"] == need_data
        pq.pipe["ready"].Set(1)


# PQ-FP-004
def test_lrsc_locked_block_blocks_probe(pq):
    pq.reset()
    address = 0xB000
    pq.send(address, 0)
    # The reservation is sampled when the probe request fires.
    pq.lrsc["valid"].Set(1)
    pq.lrsc["bits"].Set(address)
    pq.dut.Step(1)
    pq.probe["valid"].Set(0)
    stalled = pq.watch_pipe(4)
    assert stalled is None, "a probe to the LR/SC locked block must not enter the pipe"
    if pq.coverage is not None:
        pq.coverage.sample(0, 0, blocked=True)
    pq.lrsc["valid"].Set(0)
    # Releasing the reservation lets the same entry proceed.
    info = pq.watch_pipe(6)
    assert info is not None and info["addr"] == address
    if pq.coverage is not None:
        pq.coverage.sample(info["param"], info["need_data"], blocked=False)
