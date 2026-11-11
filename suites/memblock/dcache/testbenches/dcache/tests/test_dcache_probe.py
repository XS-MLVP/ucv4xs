"""Probe acknowledgement through the integrated DCache B/C channels."""
from __future__ import annotations

from suites.memblock.dcache.testbenches.shared.env.execution import step
from suites.memblock.dcache.testbenches.dcache.env import DcacheEnv
from suites.memblock.dcache.testbenches.dcache.coverage import DCacheCoverage


def line_words(base: int) -> list[int]:
    return [int.from_bytes(bytes(((base + beat * 32 + i) & 0xFF) for i in range(32)),
                           "little") for beat in range(2)]


def test_probe_ack(dut_factory):
    dut = dut_factory("dcache")
    dc = DcacheEnv(dut, DCacheCoverage())
    dc.reset()
    base = 0x8000
    beats = line_words(base)
    dc.load_once(0, base, base, context="lane0 cold")
    dc.service_miss(base, data_beats=beats, context="probe prime")
    for _ in range(8):
        step(dc)
    handshake = dc.transmit_probe(0, base, param=0)
    assert handshake.accepted, "B channel must accept the probe"
    response = handshake.response
    assert response is not None, "probe must produce a C-channel acknowledgement"
    assert response.opcode in (4, 5), response
    assert response.address == base, response
