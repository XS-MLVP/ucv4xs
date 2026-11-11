"""Pure independent FIFO/UID answers and real observer/lifecycle controls."""
import asyncio
from dataclasses import replace

import pytest

from suites.frontend.ftq.testbenches.resolve_queue.checker.transactions import ResolveTransactions
from suites.frontend.ftq.testbenches.resolve_queue.transactions.cycle import ResolveInput
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Branch
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Training

pytestmark = pytest.mark.selftest


def report(index=5, **changes):
    return ResolveReport(**(dict(index=index, pc=0x1000, offset=1, target=0x3000) | changes))


def expected(index=5, *, flag=0, offsets=(1,), pc=0x1000, target=0x3000):
    return Training(index, flag, pc, tuple(Branch(position=offset, target=target, taken=1,
                                                mispredict=1, branch_type=1, ras_action=0) for offset in offsets))


def pure_slot(checker, slot, frame, before, after):
    checker.advance_slot(frame, slot, before, after, slot * 2)
    checker.audit()


def test_input_owned_order_remains_distinct_for_identical_report_payloads():
    checker = ResolveTransactions()
    value = report()
    pure_slot(checker, 1, ResolveInput(backend=(value, value, None), ifu=value), None, None)
    pure_slot(checker, 2, ResolveInput(), expected(offsets=(1, 1, 1)), expected(offsets=(1, 1, 1)))
    pure_slot(checker, 3, ResolveInput(ready=True), expected(offsets=(1, 1, 1)), None)
    receipt = checker.receipt()
    assert receipt['accepted'] == ((0, 1, 0), (0, 1, 1), (0, 1, 3))
    assert tuple(item.action.uid for item in receipt['terminals']) == receipt['accepted']
    assert {item.status for item in receipt['terminals']} == {'completed'}


def test_halfword_position_uses_start_alignment_not_raw_offset_only():
    checker = ResolveTransactions()
    frame = ResolveInput(backend=(report(pc=0x100F, offset=16), None, None))
    pure_slot(checker, 1, frame, None, None)
    value = expected(pc=0x100F, offsets=(31,))
    pure_slot(checker, 2, ResolveInput(), value, value)
    # Frozen historical wrong answer (raw offset16) must be distinguished.
    with pytest.raises(AssertionError, match='resolve_queue'):
        checker.scoreboard.check(expected=value, actual=expected(pc=0x100F, offsets=(16,)))


def test_full_branch_row_drops_excess_instead_of_wrap_or_overwrite():
    checker = ResolveTransactions()
    for slot in range(1, 10):
        frame = ResolveInput(backend=(report(offset=slot), None, None))
        pure_slot(checker, slot, frame, None, None)
    value = expected(offsets=tuple(range(1, 9)))
    pure_slot(checker, 10, ResolveInput(), value, value)
    receipt = checker.receipt()
    assert len(receipt['accepted']) == 8
    assert [(item.action.uid, item.status) for item in receipt['terminals']] == [
        ((0, 9, 0), 'branch-capacity-rejected')]


def test_new_same_index_after_cancellation_has_a_new_entry_uid():
    checker = ResolveTransactions()
    pure_slot(checker, 1, ResolveInput(backend=(report(), None, None)), None, None)
    pure_slot(checker, 2, ResolveInput(enqueue=5), expected(), None)
    pure_slot(checker, 3, ResolveInput(backend=(report(), None, None)), None, None)
    pure_slot(checker, 4, ResolveInput(), expected(), expected())
    pure_slot(checker, 5, ResolveInput(ready=True), expected(), None)
    receipt = checker.receipt()
    assert [(item.action.uid, item.status) for item in receipt['terminals']] == [
        ((0, 1, 0), 'overwrite-cancelled'), ((0, 3, 0), 'completed')]


async def test_multiple_held_samples_are_one_pending_report_until_actual_ready(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report()])
    before = agent.receipt()
    await agent.step(5)
    assert agent.receipt() == before
    await agent.drain_all()
    assert {item.status for item in agent.receipt()['terminals']} == {'completed'}


async def test_simultaneous_sources_and_distinct_flag_get_exact_uids(resolve_queue_agent):
    agent = resolve_queue_agent
    value = report()
    await agent.resolve_mixed((value, value, report(flag=1)), ifu=value)
    await agent.drain_all()
    receipt = agent.receipt()
    assert len(receipt['accepted']) == 4 and not receipt['pending']
    assert len({item.action.uid for item in receipt['terminals']}) == 4
    assert [item.action.uid[-1] for item in receipt['terminals']] == [0, 1, 3, 2]


@pytest.mark.parametrize('mutation', ('missing', 'identity', 'payload', 'branch', 'valid-mask', 'extra'))
async def test_real_output_mutation_fails_the_automatic_path(resolve_queue_factory, monkeypatch, mutation):
    with pytest.raises(AssertionError, match='resolve_queue'):
        async with resolve_queue_factory() as agent:
            original = agent.training_monitor.sample_fn

            def corrupt(dut):
                value = original(dut)
                if value is None:
                    return expected() if mutation == 'extra' else None
                if mutation == 'missing':
                    return None
                if mutation == 'identity':
                    return replace(value, flag=value.flag ^ 1)
                if mutation == 'payload':
                    return replace(value, start_pc=value.start_pc ^ 1)
                if mutation == 'branch':
                    branch = replace(value.branches[0], target=value.branches[0].target ^ 1)
                    return replace(value, branches=(branch, *value.branches[1:]))
                if mutation == 'valid-mask':
                    return replace(value, valid_mask=value.valid_mask << 1)
                return value

            monkeypatch.setattr(agent.training_monitor, 'sample_fn', corrupt)
            await agent.resolve([report()])


async def test_mismatch_swallowed_by_caller_cannot_be_cleared_with_reset(resolve_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='resolve_queue'):
        async with resolve_queue_factory() as agent:
            original = agent.training_monitor.sample_fn
            monkeypatch.setattr(agent.training_monitor, 'sample_fn', lambda _: None)
            try:
                await agent.resolve([report()])
            except AssertionError:
                monkeypatch.setattr(agent.training_monitor, 'sample_fn', original)
                for operation in (agent.finish, agent.reset):
                    with pytest.raises(RuntimeError, match='unreconciled'):
                        await operation()
                raise


async def test_finish_does_not_invent_ready_to_discharge_accepted_reports(resolve_queue_factory):
    with pytest.raises(AssertionError, match='explicitly drain'):
        async with resolve_queue_factory() as agent:
            await agent.resolve([report()])
            await agent.finish()


async def test_backend_filter_and_capacity_rejection_have_no_response_debt(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(branch_type=2, mispredict=0), report(ras_action=1)])
    await agent.resolve([report(ras_action=1)], source='ifu')
    for index in range(11):
        await agent.resolve([report(10 + index)])
    await agent.resolve([report(30)])
    await agent.drain_all()
    receipt = agent.receipt()
    assert len(receipt['offered']) == 15 and len(receipt['accepted']) == 12
    states = [item.status for item in receipt['terminals']]
    assert states.count('backend-filtered') == 2
    assert states.count('capacity-rejected') == 1
    assert states.count('completed') == 12 and not receipt['pending']


async def test_redirect_and_reset_cancel_exact_report_sets_not_new_equal_payloads(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5), report(6), report(7)])
    old = agent.receipt()['accepted']
    await agent.redirect(5)
    await agent.drain_all()
    await agent.resolve([report(5)])
    previous = agent.receipt()['accepted'][-1]
    await agent.reset()
    await agent.resolve([report(5)])
    fresh = agent.receipt()['accepted'][-1]
    await agent.drain_all()
    terminals = {item.action.uid: item.status for item in agent.receipt()['terminals']}
    assert terminals[old[0]] == terminals[fresh] == 'completed'
    assert {uid for uid, status in terminals.items() if status == 'redirect-cancelled'} == set(old[1:])
    assert terminals[previous] == 'reset-cancelled' and previous[0] != fresh[0]


async def test_unknown_late_source_cannot_partially_drive_or_change_the_model(resolve_queue_agent):
    agent = resolve_queue_agent
    before = agent.receipt()
    count = agent.dut.sampled_cycles
    with pytest.raises(ValueError, match='validated ResolveReport'):
        await agent.resolve_mixed((report(),), ifu=object())
    assert agent.receipt() == before and agent.dut.sampled_cycles == count


async def test_sdk_all_input_ownership_cannot_be_duplicated(resolve_queue_agent):
    from suites.frontend.ftq.testbenches.resolve_queue.env.driver.slots import ResolveInputDriver
    agent = resolve_queue_agent
    driver = ResolveInputDriver(agent.dut, agent.ports)
    with pytest.raises(RuntimeError, match='already have a driver'):
        async with driver:
            raise AssertionError('duplicate native driver was admitted')


async def test_public_reference_error_cannot_be_swallowed_then_reset(resolve_queue_factory):
    with pytest.raises(RuntimeError, match='prior public reference failure'):
        async with resolve_queue_factory() as agent:
            with pytest.raises(AssertionError, match='resolve_queue.reference'):
                agent.checker.check(expected())  # Empty independent model.
            await agent.reset()


async def test_ready_finish_budget_is_not_a_silent_partial_drain(resolve_queue_factory):
    with pytest.raises(AssertionError, match='budget exhausted'):
        async with resolve_queue_factory() as agent:
            await agent.resolve([report(index) for index in (5, 6, 7)])
            await agent.ready(True)
            await agent.finish(cycles=2)


async def test_grace_window_cancels_new_younger_reports_at_the_next_declared_boundary(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5)])
    await agent.cycle(ResolveInput(redirect=(0, 5)))
    await agent.resolve([report(6)])
    await agent.drain_all()
    receipt = agent.receipt()
    assert [item.status for item in receipt['terminals']].count('redirect-cancelled') == 1
    assert [item.status for item in receipt['terminals']].count('completed') == 1


async def test_cancelled_actual_input_cannot_be_reassociated_to_a_later_source(resolve_queue_factory, monkeypatch):
    with pytest.raises(asyncio.CancelledError):
        async with resolve_queue_factory() as agent:
            sent = agent.input_driver.send
            reached = asyncio.Event()

            async def lost_receipt(frame):
                await sent(frame)
                reached.set()
                await asyncio.Event().wait()

            monkeypatch.setattr(agent.input_driver, 'send', lost_receipt)
            work = asyncio.create_task(agent.resolve([report()]))
            await reached.wait()
            work.cancel()
            try:
                await work
            except asyncio.CancelledError:
                with pytest.raises(RuntimeError, match='unreconciled'):
                    agent.receipt()
                with pytest.raises(RuntimeError, match='unreconciled'):
                    await agent.finish()
                raise


async def test_planned_input_and_real_pins_cannot_diverge_silently(resolve_queue_factory, monkeypatch):
    with pytest.raises(AssertionError, match='resolve_queue'):
        async with resolve_queue_factory() as agent:
            encode = agent.input_driver.ports.encode

            def wrong(frame):
                values = encode(frame)
                if frame.backend[0] is not None:
                    values['io_backendResolve_0_bits_target_addr'] ^= 1
                return values

            # Mutate the SDK drive operation, not the independent planned
            # encoder used to check the actual DriveStable input snapshot.
            from toffee.data import drive_data

            async def drive_wrong(frame):
                drive_data(agent.ports.bits, wrong(frame), 'injected-drive')
                try:
                    return await agent.dut.edge(1)
                finally:
                    drive_data(agent.ports.bits, encode(ResolveInput(ready=frame.ready)), 'injected-idle')
                    agent.dut.refresh()

            monkeypatch.setattr(agent.input_driver, '_drive_one', drive_wrong)
            await agent.resolve([report()])


@pytest.mark.parametrize('bad', (True, 0, -1, 1.5, '2'))
async def test_bad_wait_and_reset_budget_leave_every_uid_and_cycle_unchanged(resolve_queue_agent, bad):
    agent = resolve_queue_agent
    before, count = agent.receipt(), agent.dut.sampled_cycles
    for operation in (lambda: agent.step(bad), lambda: agent.wait_training(bad), lambda: agent.reset(asserted=bad)):
        with pytest.raises(ValueError, match='positive integer'):
            await operation()
    assert agent.receipt() == before and agent.dut.sampled_cycles == count


async def test_one_slot_services_old_ready_and_new_unrelated_report_atomically(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(5)])
    old = agent.receipt()['accepted'][0]
    await agent.cycle(ResolveInput(backend=(report(6), None, None), ready=True))
    receipt = agent.receipt()
    assert receipt['pending'] == (receipt['accepted'][-1],)
    assert receipt['terminals'][0].action.uid == old and receipt['terminals'][0].status == 'completed'
    assert agent.training().index == 6
    await agent.finish()


async def test_same_entry_merge_defers_consumption_even_when_ready_is_already_high(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report()])
    await agent.cycle(ResolveInput(backend=(report(offset=2), None, None), ready=True))
    receipt = agent.receipt()
    assert len(receipt['pending']) == 2 and not receipt['terminals']
    await agent.step(1)
    assert not agent.receipt()['pending']
    assert len(agent.receipt()['terminals']) == 2


async def test_same_slot_ready_completion_is_not_relabelled_as_redirect_cancellation(resolve_queue_agent):
    agent = resolve_queue_agent
    await agent.resolve([report(6), report(7)])
    owners = agent.receipt()['accepted']
    await agent.cycle(ResolveInput(ready=True, redirect=(0, 5)))
    states = {item.action.uid: item.status for item in agent.receipt()['terminals']}
    assert states == {owners[0]: 'completed', owners[1]: 'redirect-cancelled'}
    await agent.finish()


def test_input_slot_owns_its_lane_vector_and_rejects_unvalidated_encoder_payloads():
    from suites.frontend.ftq.testbenches.resolve_queue.env.driver.encoding import encode
    values = [report(), None, None]
    frame = ResolveInput(backend=values)
    values[0] = None
    assert frame.backend[0] == report()
    with pytest.raises(AttributeError):
        frame.backend = (None,) * 3
    for bad in (object(), dict(index=0), None):
        with pytest.raises(ValueError, match='validated ResolveReport'):
            encode(bad)


def test_entry_start_pc_remains_bound_to_its_first_input_owner():
    checker = ResolveTransactions()
    pure_slot(checker, 1, ResolveInput(backend=(report(pc=0x1000), None, None)), None, None)
    pure_slot(checker, 2, ResolveInput(backend=(report(pc=0x1001), None, None)), None, None)
    value = expected(pc=0x1000, offsets=(1, 2))
    pure_slot(checker, 3, ResolveInput(), value, value)
    # This is a pure ownership invariant/invalid-producer control, not native
    # proof of a same-FTQ entry being produced with two different start PCs.
    with pytest.raises(AssertionError, match='resolve_queue'):
        checker.scoreboard.check(expected=value, actual=replace(value, start_pc=0x1001))
