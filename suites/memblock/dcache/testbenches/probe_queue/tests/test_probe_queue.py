"""ProbeQueue UT: B-channel probe acceptance, MainPipe request encoding, LR/SC block."""
from __future__ import annotations

import pytest

from suites.memblock.dcache.testbenches.shared.env.execution import step
from suites.memblock.dcache.testbenches.probe_queue.coverage import ProbeQueueCoverage
from suites.memblock.dcache.testbenches.probe_queue.env import ProbeEnv
from suites.memblock.dcache.testbenches.probe_queue.env import ProbeRequest


@pytest.fixture
def pq(dut_factory):
    return ProbeEnv(dut_factory("probe_queue"), ProbeQueueCoverage())


# PQ-FP-001
def test_probe_to_b_requests_data(pq):
    pq.reset()
    address = 0x8000
    assert pq.can_accept_probe()
    acceptance = pq.transmit_probe(ProbeRequest(address, param=0))
    assert acceptance.fired, "idle probe queue must accept the B request"
    info = pq.watch_pipe(6)
    assert info is not None, "probe must reach the main pipe"
    if pq.coverage is not None:
        pq.coverage.sample(info.param, info.need_data, blocked=False)
    assert info.param == 0
    assert info.addr == address
    assert info.need_data in (0, 1)


# PQ-FP-002
def test_probe_to_n_and_to_t(pq):
    pq.reset()
    for param, need_data in ((0, 0), (1, 0), (2, 1)):
        address = 0x9000 + param * 0x40
        acceptance = pq.transmit_probe(
            ProbeRequest(address, param, need_data=bool(need_data)))
        assert acceptance.fired
        info = pq.watch_pipe(6)
        assert info is not None
        if pq.coverage is not None:
            pq.coverage.sample(info.param, info.need_data, blocked=False)
        assert info.param == param
        assert info.addr == address
        assert info.need_data == need_data
        pq.hold_mainpipe_ready(True)


# PQ-FP-003
def test_lrsc_locked_block_blocks_probe(pq):
    pq.reset()
    address = 0xB000
    pq.offer_probe(ProbeRequest(address, 0))
    # The reservation is sampled when the probe request fires.
    pq.lock_lrsc_block(address)
    acceptance = pq.settle_probe()
    assert acceptance.fired
    stalled = pq.watch_pipe(4)
    assert stalled is None, "a probe to the LR/SC locked block must not enter the pipe"
    if pq.coverage is not None:
        pq.coverage.sample(0, 0, blocked=True)
    pq.unlock_lrsc_block()
    # Releasing the reservation lets the same entry proceed.
    info = pq.watch_pipe(6)
    assert info is not None and info.addr == address
    if pq.coverage is not None:
        pq.coverage.sample(info.param, info.need_data, blocked=False)


# PQ-FP-004: accepted request is held under MainPipe backpressure
def test_probe_transaction_holds_payload_under_backpressure(pq):
    pq.reset()
    pq.hold_mainpipe_ready(False)
    address = 0xA000
    acceptance = pq.transmit_probe(ProbeRequest(address, 0))
    assert acceptance.fired
    first = pq.watch_pipe(3)
    assert first is not None and first.addr == address
    # Ready is held low for several real edges: the same entry must keep the
    # same payload and identity instead of being retried or dropped.
    held = pq.observe_pipe_window(3)
    assert len(held) == 3, held
    assert all(item == first for item in held), (first, held)
    # Releasing the consumer must actually consume the request, not just hide it.
    pq.hold_mainpipe_ready(True)
    consumed = False
    for _ in range(4):
        step(pq)
        if pq.watch_pipe(1) is None:
            consumed = True
            break
    assert consumed, "accepted request must leave the pipe once the consumer is ready"


# PQ transaction domain: reject physically illegal probe encodings at the fixture edge
@pytest.mark.selftest
def test_probe_request_rejects_illegal_domain():
    with pytest.raises(ValueError):
        ProbeRequest(0x8001, param=0)
    with pytest.raises(ValueError):
        ProbeRequest(0x8000, param=3)
    with pytest.raises(ValueError):
        ProbeRequest(-64, param=0)
    with pytest.raises(ValueError):
        ProbeRequest(1 << 48, param=0)
    with pytest.raises(TypeError):
        ProbeRequest(0x8000, param=0, need_data=object())
    with pytest.raises(TypeError):
        ProbeRequest(0x8000, param=0, need_data=1)

    # The combined API validates its budget before the offer writes the B
    # payload, so a rejected limit leaves no unsettled request or reservation
    # change behind.
    class FakeSignal:
        def __init__(self, value=0):
            self.value = value

        def Set(self, value):
            self.value = value

    env = ProbeEnv.__new__(ProbeEnv)
    env.probe = {name: FakeSignal() for name in ("valid", "param", "address", "data")}
    env.pipe = {name: FakeSignal() for name in
                ("valid", "param", "need_data", "addr", "id")}
    env.pipe["ready"] = FakeSignal(1)
    env.lrsc = {"valid": FakeSignal(0), "bits": FakeSignal(0x40)}
    env.update_resv = FakeSignal()
    env._pending = None
    env.lock_lrsc_block(0xB000)
    before = (env.probe["valid"].value, env.probe["address"].value,
              env._pending, env.lrsc["valid"].value, env.lrsc["bits"].value)
    for bad in (0, -1, 0.5, "8"):
        with pytest.raises(ValueError):
            env.transmit_probe(ProbeRequest(0x8000, 0), limit=bad)
    after = (env.probe["valid"].value, env.probe["address"].value,
             env._pending, env.lrsc["valid"].value, env.lrsc["bits"].value)
    assert after == before, (before, after)
