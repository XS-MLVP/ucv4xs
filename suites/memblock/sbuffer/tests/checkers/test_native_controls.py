"""Controlled bench faults: exercise complete cases, never label them RTL bugs."""
from dataclasses import replace

import pytest

from suites.memblock.sbuffer.execution import execution
from suites.memblock.sbuffer.sbuffer.model import Enq
from suites.memblock.sbuffer.tests.sbuffer.test_sbuffer import (
    test_each_lane_merge_and_forward as merge_case,
    test_timeout_writeout_all_lanes as timeout_case,
)
from suites.memblock.sbuffer.tests.sbuffer.test_transactions import (
    test_active_bytes_override_inflight_with_old_byte_fallback as priority_case,
    test_cmo_exit_does_not_leave_a_fence_drain_with_sq_nonempty as cmo_case,
)

pytestmark = pytest.mark.selftest


async def test_reject_all_cannot_leave_the_complete_timeout_case_green(sbuffer_env, monkeypatch):
    ports = sbuffer_env._ports
    encode, capture = ports.encode, ports.capture

    def reject_inputs(command):
        # No enqueue actually reaches the unmodified DUT; report zero accepts.
        return encode(replace(command, enqueues=()))

    pending = []

    def encode_with_offer(command):
        pending[:] = command.enqueues
        return reject_inputs(command)

    def captured(event):
        observed = capture(event)
        # Preserve offered identity: fail on required acceptance, not setup.
        return replace(observed, enqueues=tuple((port, req, False) for port, req in pending))

    monkeypatch.setattr(ports, 'encode', encode_with_offer)
    # SyncSingleCycleDriver captured the original bound encoder on construction.
    monkeypatch.setattr(sbuffer_env._driver, 'encoder', encode_with_offer)
    monkeypatch.setattr(ports, 'capture', captured)
    with pytest.raises(AssertionError, match='ready .* != expected'):
        await timeout_case(sbuffer_env)
    assert sbuffer_env.ledger.enqueue_offered == 1
    assert sbuffer_env.ledger.enqueue_accepted == 0


async def test_missing_output_cannot_leave_the_complete_merge_case_green(sbuffer_env, monkeypatch):
    ports = sbuffer_env._ports
    capture, request = ports.capture, ports.request

    def hidden(event):
        observed = capture(event)
        return replace(observed, request=None, request_fire=False)

    def status():
        return replace(original_status(), request_pending=False)

    original_status = ports.status
    monkeypatch.setattr(ports, 'capture', hidden)
    monkeypatch.setattr(ports, 'status', status)
    with pytest.raises(TimeoutError, match='drain budget exhausted'):
        await merge_case(sbuffer_env)
    assert len(sbuffer_env.model.lines) == 8
    # The actual DUT still offered a write: this fault was at the observation
    # boundary, not an RTL failure or a real DUT ready problem.
    assert request() is not None


async def test_cmo_classification_fault_is_detected_by_the_successor_case(sbuffer_env, monkeypatch):
    ports = sbuffer_env._ports
    encode = ports.encode

    def classified_as_fence(command):
        return encode(replace(command, controls=replace(command.controls, cmo=False)))

    monkeypatch.setattr(ports, 'encode', classified_as_fence)
    monkeypatch.setattr(sbuffer_env._driver, 'encoder', classified_as_fence)
    with pytest.raises(AssertionError, match='CMO classification.*unexpected dcache request'):
        await cmo_case(sbuffer_env)


async def test_reversed_priority_oracle_is_not_silently_accepted(sbuffer_env, monkeypatch):
    model = sbuffer_env.model
    expected = model.forward
    exercised = []

    def reversed_priority(vaddr, paddr):
        mask, data, mismatch = expected(vaddr, paddr)
        lane = (paddr >> 4) & 3
        for line in model.lines:
            if line.vtag == vaddr >> 6 and line.inflight:
                for byte in range(16):
                    if (line.mask[lane] >> byte) & 1:
                        data[byte] = line.data[lane][byte]
                exercised.append(line.uid)
        return mask, data, mismatch

    monkeypatch.setattr(model, 'forward', reversed_priority)
    with pytest.raises(AssertionError, match='forward byte'):
        await priority_case(sbuffer_env)
    assert exercised


async def test_uncompleted_writeback_cannot_exit_execution_normally(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    with pytest.raises(AssertionError, match='uncompleted writeback obligations'):
        async with execution(env):
            await env.reset()
            await env.enqueue([Enq(10, 12, 0, 15, 0x11111111)])
            snap = await env.wait_req('forgotten response')
            await env.accept(snap, 'timeout')
