"""ProbeQueue UT: B-channel probe acceptance, MainPipe request encoding, LR/SC block."""
from __future__ import annotations

import pytest

from suites.memblock.dcache.execution import step

from suites.memblock.dcache.probe_queue.coverage import ProbeQueueCoverage
from suites.memblock.dcache.probe_queue.env import ProbeEnv


@pytest.fixture
def pq(dut_factory):
    return ProbeEnv(dut_factory("probe_queue"), ProbeQueueCoverage())


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
    step(pq)
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
