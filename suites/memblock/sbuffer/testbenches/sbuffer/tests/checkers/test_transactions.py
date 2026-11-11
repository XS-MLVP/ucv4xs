"""Bench observation/driver controls, not injected RTL or functional credit."""
from dataclasses import FrozenInstanceError, replace
import pytest

from suites.memblock.sbuffer.testbenches.sbuffer.checker import WritebackLedger
from suites.memblock.sbuffer.testbenches.sbuffer.env import SbufferEnv
from suites.memblock.sbuffer.testbenches.sbuffer.model import Enq
from suites.memblock.sbuffer.testbenches.sbuffer.model import SbufferModel
from suites.memblock.sbuffer.testbenches.sbuffer.env.ports import SbufferPorts
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Cycle
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Observation
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Request
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Status

pytestmark = pytest.mark.selftest


def populated():
    model = SbufferModel()
    model.enqueue([Enq(1, 2, 0, 15, 0x44332211)])
    return WritebackLedger(model)


def request(ledger, slot=3, index=0):
    line = ledger.model.lines[index]
    return Request(slot, line.ptag << 6, line.vtag << 6, line.line_mask(), line.line_data())


def observation(**fields):
    return replace(Observation(False, (), None, False, None, None), **fields)


def test_unaccepted_offer_is_not_a_response_identity():
    ledger = populated()
    snap = ledger.inspect(request(ledger))
    with pytest.raises(AssertionError, match='stale or unaccepted'):
        ledger.require_pending(snap)
    with pytest.raises(AssertionError, match='without previously accepted'):
        ledger.observe(observation(hit=snap.id), 2)
    assert not ledger.reserved


def test_valid_low_cannot_be_counted_as_acceptance():
    ledger = populated()
    assert ledger.observe(observation(), 2) is None
    assert not ledger.pending and not ledger.events


def test_accept_hit_and_duplicate_response():
    ledger = populated()
    snap = ledger.observe(observation(request=request(ledger), request_fire=True), 2)
    assert snap.uid == 0 and snap.attempt == 1
    with pytest.raises(FrozenInstanceError):
        snap.addr = 0
    ledger.require_pending(snap)
    ledger.observe(observation(hit=snap.id), 4)
    assert not ledger.model.lines
    ledger.finish()
    with pytest.raises(AssertionError, match='previously accepted'):
        ledger.observe(observation(hit=snap.id), 6)


def test_pending_slot_cannot_be_reused_for_an_unrelated_line():
    ledger = populated()
    ledger.accept(request(ledger), 2)
    ledger.model.enqueue([Enq(4, 5, 0, 1, 0x22)])
    with pytest.raises(AssertionError, match='still awaiting response'):
        ledger.accept(request(ledger, index=1), 4)


def test_retry_keeps_slot_and_rejects_the_old_attempt_handle():
    ledger = populated()
    raw = request(ledger)
    first = ledger.accept(raw, 2)
    ledger.respond(first.id, 'replay', 4)
    with pytest.raises(AssertionError, match='payload must match one eligible'):
        ledger.inspect(replace(raw, id=4))
    retry = ledger.accept(raw, 8)
    assert retry.retry and retry.uid == first.uid and retry.attempt == 2
    with pytest.raises(AssertionError, match='stale or unaccepted'):
        ledger.require_pending(first)
    ledger.require_pending(retry)
    ledger.respond(retry.id, 'hit', 10)
    ledger.finish()


@pytest.mark.parametrize('response', ['none', 'replay'])
def test_finish_rejects_accepted_or_replay_obligations(response):
    ledger = populated()
    snap = ledger.accept(request(ledger), 2)
    if response == 'replay':
        ledger.respond(snap.id, response, 4)
    with pytest.raises(AssertionError, match='uncompleted writeback'):
        ledger.finish()
    ledger.reset(6)
    ledger.finish()
    assert ledger.events[-1].kind == 'reset_cancelled'


def test_reset_does_not_reuse_a_line_identity():
    ledger = populated()
    old = ledger.accept(request(ledger), 2)
    ledger.reset(4)
    ledger.model.enqueue([Enq(1, 2, 0, 15, 0x44332211)])
    fresh = ledger.accept(request(ledger), 6)
    assert fresh.uid != old.uid
    with pytest.raises(AssertionError, match='stale or unaccepted'):
        ledger.require_pending(old)


@pytest.mark.parametrize('field', ['addr', 'vaddr'])
def test_full_line_address_not_just_tag_is_checked(field):
    ledger = populated()
    raw = request(ledger)
    with pytest.raises(AssertionError, match='unaligned'):
        ledger.inspect(replace(raw, **{field: getattr(raw, field) | 1}))
    assert ledger.inspect(raw).addr == 64


def test_invalid_data_bytes_are_ignored_but_valid_bytes_are_checked():
    ledger = populated()
    raw = request(ledger)
    assert ledger.inspect(replace(raw, data=raw.data ^ (255 << 80))) == ledger.inspect(raw)
    with pytest.raises(AssertionError, match='payload must match'):
        ledger.inspect(replace(raw, data=raw.data ^ 1))


def test_equal_payload_different_history_does_not_rebind_a_retry():
    ledger = populated()
    raw = request(ledger)
    old = ledger.accept(raw, 2)
    ledger.model.enqueue([Enq(1, 2, 0, 15, 0x44332211)])
    fresh_uid = ledger.model.lines[-1].uid
    ledger.respond(old.id, 'replay', 4)
    retry = ledger.accept(raw, 6)
    assert retry.uid == old.uid != fresh_uid
    ledger.respond(retry.id, 'hit', 8)
    successor = ledger.accept(raw, 10)  # A released slot may be legally reused.
    assert successor.uid == fresh_uid != retry.uid


def test_offered_but_unaccepted_line_is_not_an_active_merge_target():
    ledger = populated()
    raw = request(ledger)
    younger = Enq(1, 2, 0, 3, 0x2222)
    assert ledger.observe(observation(request=raw, enqueues=((0, younger, True),)), 2) is None
    assert len(ledger.model.lines) == 2
    assert not ledger.pending and not ledger.reserved
    offered = ledger.inspect(raw)
    with pytest.raises(AssertionError, match='stale or unaccepted'):
        ledger.require_pending(offered)
    accepted = ledger.accept(raw, 4)
    assert accepted.uid == offered.uid


def test_same_edge_hit_new_request_and_enqueue_are_all_accounted():
    ledger = populated()
    first = ledger.accept(request(ledger), 2)
    ledger.model.enqueue([Enq(4, 5, 0, 1, 0x22)])
    fresh = Enq(6, 7, 1, 1, 0x33)
    accepted = ledger.observe(observation(hit=first.id, request=request(ledger, slot=4, index=1),
                                         request_fire=True, enqueues=((0, fresh, True),)), 4)
    assert accepted.id == 4 and set(ledger.pending) == {4}
    assert {line.ptag for line in ledger.model.lines} == {4, 6}
    assert ledger.enqueue_accepted == 1
    assert [event.kind for event in ledger.events] == ['accepted', 'accepted', 'hit']


async def test_default_enqueue_cannot_succeed_with_zero_acceptance():
    env = object.__new__(SbufferEnv)
    env.model, env.coverage = SbufferModel(), None

    async def reject(**fields):
        port, req = fields['enqueues'][0]
        return observation(enqueues=((port, req, False),)), None

    env._cycle = reject
    req = Enq(1, 2, 0, 1, 3)
    with pytest.raises(AssertionError, match='ready .* != expected'):
        await env.enqueue([req])
    assert await env.enqueue([req], expect_ready=[0]) == {0: 0}


async def test_exhausted_drain_is_not_success_and_does_not_clear_state():
    env = object.__new__(SbufferEnv)
    env.model, env.coverage, env.tick = SbufferModel(), None, 0
    env.model.enqueue([Enq(1, 2, 0, 1, 3)])
    env.model.uarch_drain = True
    env.status = lambda: Status(False, False, False, False, (False, False))

    async def edge():
        env.tick += 1

    env.edge = edge
    with pytest.raises(TimeoutError, match='1 live lines'):
        await env.drain_requests('missing output', max_cycles=2)
    with pytest.raises(TimeoutError, match='1 live lines'):
        await env.drain_uarch()
    assert len(env.model.lines) == 1 and env.model.uarch_drain


def test_bad_parent_wline_and_duplicate_ports_fail_before_encoding():
    ports = object.__new__(SbufferPorts)
    # Input writes are not available in this control: invalid commands must be
    # rejected before width lookup or Bundle.drive can touch anything.
    ports.inputs = {}
    for command, error in (
        (Cycle(enqueues=((0, Enq(1, 2, 0, 1, 7, True)),)), 'only legal for zero'),
        (Cycle(enqueues=((0, Enq(1, 2, 0, 1, 7)), (0, Enq(3, 4, 0, 1, 9)))), 'unique'),
    ):
        with pytest.raises(ValueError, match=error):
            ports.encode(command)


def test_required_native_port_is_not_silently_optional():
    with pytest.raises(AttributeError):
        SbufferPorts(object())


async def test_native_driver_ownership_rejects_a_second_writer(sbuffer_env):
    from toffee import SyncSingleCycleDriver
    from suites.memblock.sbuffer.testbenches.shared.env.execution import execution
    env = sbuffer_env
    competitor = SyncSingleCycleDriver(env.dut.clock, env._ports.bits,
        idle=env._ports.encode(Cycle()), encoder=env._ports.encode, name='unauthorized-writer')
    async with execution(env):
        await env.reset()
        with pytest.raises((RuntimeError, ValueError), match='driver|owner|claim'):
            await competitor.send(Cycle())
        await env.settle(2)
