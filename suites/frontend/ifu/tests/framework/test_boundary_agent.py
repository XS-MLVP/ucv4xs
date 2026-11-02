"""Contract/schema/runtime controls; Python injection is not RTL mutation credit."""
import asyncio
from dataclasses import FrozenInstanceError, replace

import pytest
from toffee import MonitorClosedError, SyncSingleCycleDriver

from suites.frontend.ifu.instr_boundary.checker import check_boundary
from suites.frontend.ifu.instr_boundary.ports import BoundaryPorts
from suites.frontend.ifu.instr_boundary.types import BoundaryBatchMismatch, IDLE
from suites.frontend.ifu.model.boundary import BoundaryInput, predict

pytestmark = [pytest.mark.selftest, pytest.mark.feature('IFU-ENV-002')]


@pytest.mark.feature('IFU-ENV-004')
@pytest.mark.parametrize('field,value', [
    ('block0_size', 0), ('block0_size', 33), ('block0_size', 1.0),
    ('taken_valid', 2), ('block1_valid', -1), ('first_instr_is_half_rvi', '1'),
    ('taken_offset', -1), ('taken_offset', 32), ('total_end_pos', 32),
    ('maybe_rvc', -1), ('maybe_rvc', 1 << 32), ('block_sel', -1), ('block_sel', 1 << 32),
])
def test_request_domain_cannot_rely_on_native_truncation(field, value):
    with pytest.raises(ValueError):
        replace(IDLE, **{field: value})


@pytest.mark.parametrize('updates', [
    {'block0_size': 1, 'taken_valid': 1, 'taken_offset': 1},
    {'block1_valid': 0, 'block_sel': 2},
    {'block0_size': 8, 'block1_valid': 1, 'block_sel': 0},
])
def test_block_coordinates_and_taken_position_must_describe_the_producer(updates):
    with pytest.raises(ValueError, match='first block|producer block split'):
        replace(IDLE, **updates)


@pytest.mark.parametrize('indices', [(), (0,) * 31, (0,) * 33, (-1,) + (0,) * 31,
                                    (32,) + (0,) * 31])
def test_index_vector_has_no_silent_empty_default_or_overflow(indices):
    with pytest.raises(ValueError):
        replace(IDLE, index=indices)


def test_request_snapshots_mutable_lists_and_unknown_keys_fail():
    values = list(range(32))
    request = replace(IDLE, index=values)
    values[0] = 31
    assert request.index[0] == 0 and isinstance(request.index, tuple)
    with pytest.raises(FrozenInstanceError):
        request.maybe_rvc = 0
    with pytest.raises(TypeError):
        BoundaryInput(32, 0, 31, 0, 0, 0, 0, 31, total_end=31)
    assert IDLE.index == tuple(range(32))


@pytest.mark.parametrize('field,value', [('valid', (0,) * 31), ('index', (32,) * 32),
    ('is_rvc', (2,) * 32), ('first_end_is_half_rvi', 2)])
def test_incomplete_or_invalid_output_snapshots_fail_before_comparison(field, value):
    with pytest.raises(ValueError):
        replace(predict(IDLE), **{field: value})
    with pytest.raises(TypeError, match='complete semantic'):
        check_boundary(IDLE, None)


@pytest.mark.parametrize('name', ['io_req_ifuData_index_31', 'io_req_totalEndPos',
    'io_resp_rawInstrVec_0_endOffset', 'io_resp_totalEndIsHalfRvi'])
def test_required_ports_are_never_zero_defaults(instr_boundary_factory, monkeypatch, name):
    agent = instr_boundary_factory()
    with monkeypatch.context() as patch:
        patch.delattr(agent.dut, name)
        with pytest.raises(AttributeError):
            BoundaryPorts(agent.dut)


@pytest.mark.parametrize('name,width', [('io_req_fetchBlock_0_size', 5),
    ('io_req_ifuData_maybeRvcMap', 31), ('io_resp_rawInstrVec_0_index', 6),
    ('io_resp_firstEndIsHalfRvi', 2)])
def test_changed_width_requires_explicit_migration(instr_boundary_factory, monkeypatch, name, width):
    agent = instr_boundary_factory()
    signal = getattr(agent.dut, name)

    class WrongWidth:
        mWidth = width

        def __getattr__(self, field):
            return getattr(signal, field)

    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), name, WrongWidth())
        with pytest.raises(ValueError, match='native width'):
            BoundaryPorts(agent.dut)


def test_wrong_direction_or_unowned_inputs_are_binding_errors(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'io_req_totalEndPos', agent.dut.io_resp_rawInstrVec_0_index)
        with pytest.raises(ValueError, match='direction'):
            BoundaryPorts(agent.dut)
    with monkeypatch.context() as patch:
        patch.setitem(vars(agent.dut), 'new_input', agent.dut.io_req_totalEndPos)
        with pytest.raises(ValueError, match='input ownership mismatch'):
            BoundaryPorts(agent.dut)


async def test_competing_writer_is_rejected_and_legal_followup_still_works(instr_boundary):
    agent = instr_boundary
    competitor = SyncSingleCycleDriver(agent._clock, agent._ports.bits,
        idle=agent._ports.encode(IDLE), encoder=agent._ports.encode, name='competing-boundary-writer')
    try:
        with pytest.raises((RuntimeError, ValueError), match='driver|claim|owner'):
            await competitor.send(IDLE)
    finally:
        competitor.close()
    assert (await agent.analyze(IDLE)).result.valid[0] == 1


async def test_only_unconsumed_invalid_metadata_is_ignored(instr_boundary):
    observed = (await instr_boundary.analyze(IDLE)).result
    check_boundary(IDLE, observed)
    for field in ('is_rvc', 'is_cross_block', 'start_offset', 'end_offset', 'block_sel', 'index'):
        values = list(getattr(observed, field))
        values[1] ^= 1  # Invalid continuation slot; compact cannot select it.
        check_boundary(IDLE, replace(observed, **{field: tuple(values)}))
        values = list(getattr(observed, field))
        values[0] ^= 1  # Same field, now a real instruction: must be rejected.
        with pytest.raises(AssertionError, match='instr_boundary mismatch'):
            check_boundary(IDLE, replace(observed, **{field: tuple(values)}))


async def test_carry_end_offset_override_cannot_hide_other_carry_metadata(instr_boundary):
    request = replace(IDLE, first_instr_is_half_rvi=1, maybe_rvc=1)
    observed = (await instr_boundary.analyze(request)).result
    offsets = (29,) + observed.end_offset[1:]
    check_boundary(request, replace(observed, end_offset=offsets))  # Consumer rewrites this to0.
    cross = (1,) + observed.is_cross_block[1:]
    with pytest.raises(AssertionError, match='is_cross_block'):
        check_boundary(request, replace(observed, is_cross_block=cross))


def test_legacy_rtl_shaped_carry_model_is_rejected_by_the_independent_contract():
    request = BoundaryInput(1, 0, 0, 1, 0b1010, (1 << 32) - 2, 1, 3)
    correct = predict(request)
    assert correct.valid[0] == 1 and correct.is_cross_block[0] == 0
    check_boundary(request, correct)
    # The old algorithm checked !is_rvc but not actual instruction start.
    wrong = replace(correct, is_cross_block=(1,) + correct.is_cross_block[1:])
    with pytest.raises(AssertionError, match='is_cross_block'):
        check_boundary(request, wrong)


def test_expected_override_and_observed_valid_cannot_expand_the_metadata_mask():
    correct = predict(IDLE)
    valid = (0,) + correct.valid[1:]
    bad = replace(correct, valid=valid, end_offset=(29,) + correct.end_offset[1:])
    wanted = replace(correct, valid=valid)
    with pytest.raises(AssertionError, match='end_offset'):
        check_boundary(IDLE, bad, wanted)


async def test_every_consumed_field_and_pruned_constant_is_checked(instr_boundary):
    observed = (await instr_boundary.analyze(IDLE)).result
    for field in ('valid', 'is_rvc', 'is_cross_block', 'instr_end_mask', 'start_offset',
                  'end_offset', 'block_sel', 'index'):
        values = list(getattr(observed, field))
        values[0] ^= 1
        with pytest.raises(AssertionError):
            check_boundary(IDLE, replace(observed, **{field: tuple(values)}))
    for field in ('first_end_is_half_rvi', 'total_end_is_half_rvi'):
        with pytest.raises(AssertionError):
            check_boundary(IDLE, replace(observed, **{field: getattr(observed, field) ^ 1}))
    with pytest.raises(AssertionError, match='pruned_cross'):
        check_boundary(IDLE, replace(observed, is_cross_block=observed.is_cross_block[:-1] + (1,)))


async def test_task_handoffs_keep_exact_identity_and_frozen_snapshots(instr_boundary):
    first = await instr_boundary.analyze(IDLE)
    for _ in range(12):
        await asyncio.sleep(0)
    second = await instr_boundary.analyze(replace(IDLE, maybe_rvc=(1 << 32) - 1))
    assert second.sequence == first.sequence + 1 and second.sample_tick == first.sample_tick + 2
    assert first.result.valid != second.result.valid
    with pytest.raises(FrozenInstanceError):
        first.result.valid = second.result.valid


async def test_concurrent_operations_cannot_cross_associate_samples(instr_boundary):
    pending = asyncio.create_task(instr_boundary.analyze(IDLE))
    try:
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match='concurrent'):
            await instr_boundary.analyze(IDLE)
    finally:
        await pending


async def test_closed_monitor_cannot_produce_a_passing_window(instr_boundary_factory):
    agent = instr_boundary_factory()
    with pytest.raises(MonitorClosedError):
        async with agent.running():
            await agent.analyze(IDLE)
            await agent._monitor.aclose()
            await agent.analyze(IDLE)


async def test_stale_tick_is_not_accepted_even_with_identical_payload(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(AssertionError, match='stale or missing snapshot'):
        async with agent.running():
            await agent.analyze(IDLE)
            recv = agent._monitor.recv

            async def stale():
                transfer = await recv()
                return replace(transfer, event=replace(transfer.event, tick=transfer.event.tick - 2))

            monkeypatch.setattr(agent._monitor, 'recv', stale)
            await agent.analyze(IDLE)


async def test_stale_payload_cannot_replace_the_current_window(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(AssertionError, match='instr_boundary mismatch'):
        async with agent.running():
            first = await agent.analyze(IDLE)
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: first.result)
            await agent.analyze(replace(IDLE, maybe_rvc=(1 << 32) - 1))


async def test_missing_snapshot_is_not_a_passing_empty_window(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(TypeError, match='complete semantic'):
        async with agent.running():
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: None)
            await agent.analyze(IDLE)
    assert agent.checked_slots == 0 and agent.sampled_slots == 1


async def test_whole_finite_batch_is_checked_despite_multiple_payload_failures(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    captured = 0
    with pytest.raises(BoundaryBatchMismatch) as caught:
        async with agent.running():
            capture = agent._monitor.capture

            def corrupt(event):
                nonlocal captured
                index, captured = captured, captured + 1
                observed = capture(event)
                return replace(observed, valid=(0,) + observed.valid[1:]) if index in (1, 3) else observed

            monkeypatch.setattr(agent._monitor, 'capture', corrupt)
            await agent.analyze_many([IDLE] * 5)
    assert captured == agent.checked_slots == 5
    assert caught.value.summary.checked == 5 and caught.value.summary.failed_indices == (1, 3)


async def test_batch_does_not_downgrade_transport_failure_to_a_dut_comparison(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    received = 0
    with pytest.raises(AssertionError, match='stale or missing snapshot'):
        async with agent.running():
            await agent.analyze_many([IDLE])
            assert agent.last_batch.checked == 1
            recv = agent._monitor.recv

            async def stale_second():
                nonlocal received
                observed = await recv()
                received += 1
                return replace(observed, event=replace(observed.event, tick=observed.event.tick - 2)) if received == 2 else observed

            monkeypatch.setattr(agent._monitor, 'recv', stale_second)
            await agent.analyze_many([IDLE] * 5)
    assert received == 2 and agent.checked_slots == 2 and agent.last_batch is None


async def test_finish_checks_idle_instead_of_discarding_the_last_payload(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(AssertionError, match='instr_boundary mismatch'):
        async with agent.running():
            old = await agent.analyze(replace(IDLE, maybe_rvc=(1 << 32) - 1))
            monkeypatch.setattr(agent._monitor, 'capture', lambda _: old.result)


async def test_cancelled_or_swallowed_failure_cannot_finish_cleanly(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(RuntimeError, match='unreconciled evaluation'):
        async with agent.running():
            pending = asyncio.create_task(agent.analyze(IDLE))
            await asyncio.sleep(0)
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending


async def test_restoring_monitor_after_swallowed_failure_is_not_success(instr_boundary_factory, monkeypatch):
    agent = instr_boundary_factory()
    with pytest.raises(RuntimeError, match='unreconciled evaluation'):
        async with agent.running():
            with monkeypatch.context() as patch:
                patch.setattr(agent._monitor, 'capture', lambda _: replace(predict(IDLE), valid=(0,) * 32))
                with pytest.raises(AssertionError):
                    await agent.analyze(IDLE)


async def test_lifecycle_and_rejected_work_do_not_advance_slots(instr_boundary_factory):
    agent = instr_boundary_factory()
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.analyze(IDLE)
    async with agent.running():
        first = await agent.analyze(IDLE)
        for batch in ([], {}, (request for request in [IDLE])):
            with pytest.raises(ValueError, match='finite sequence'):
                await agent.analyze_many(batch)
        with pytest.raises(TypeError, match='semantic BoundaryInput'):
            await agent.analyze({})
        second = await agent.analyze(IDLE)
        assert second.sample_tick == first.sample_tick + 2
        await agent.finish()
        await agent.finish()
        with pytest.raises(RuntimeError, match='finished'):
            await agent.analyze(IDLE)
    with pytest.raises(RuntimeError, match='fixture-managed Execution'):
        await agent.analyze(IDLE)
