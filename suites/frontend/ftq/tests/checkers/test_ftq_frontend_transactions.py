"""Whole top automatic-path controls. Observation injections are selftests."""
from dataclasses import replace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.ftq.ftq.checker.requests import geometry, prefetch_case
from suites.frontend.ftq.ftq.checker.redirect import RedirectSchedule
from suites.frontend.ftq.ftq.checker.training import TrainingPath
from suites.frontend.ftq.ftq.transaction.cycle import FtqInput
from suites.frontend.ftq.ftq.transaction.types import BackendRedirect, IfuRedirect, Consumers, Prediction, PredictionSpec
from suites.frontend.ftq.resolve_queue.transaction.types import ResolveReport

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('start,end,next_line,cross,bank0,bank1', (
    (0x10, 31, 0x30, True, 0xf0, 0x0f), (0x08, 19, 0x28, False, 0x1c, 0),
    (0x00, 31, 0x20, False, 0xff, 0), (0x1f, 15, 0x3f, False, 0x80, 0),
))
def test_independent_byte_interval_answers(start, end, next_line, cross, bank0, bank1):
    value = geometry(start, end)
    assert (value.next_line, value.cross_line, value.bank0, value.bank1) == (next_line, cross, bank0, bank1)


@pytest.mark.parametrize('first,second,expected', (
    ((0, 3), (0x10, 3), 1), ((0x10, 31), (0x20, 3), 2),
    ((0x60, 3), (0x50, 31), 4), ((0, 3), (0x20, 3), 8),
    ((0x7f0, 3), (0x800, 3), 0),
))
def test_onehot_two_prefetch(first, second, expected):
    assert prefetch_case(geometry(*first), geometry(*second), eligible=True) == expected
    assert prefetch_case(geometry(*first), geometry(*second), eligible=False) == 0


def test_receiver_keeps_registered_ifu_resolve_separate_from_redirect_arbitration():
    model = RedirectSchedule()
    frame = FtqInput(backend_redirect=BackendRedirect(1), ifu_redirect=IfuRedirect(2))
    before = model.advance(frame, 0, 1, [None] * 64)
    after = model.view(frame, 0, 1)
    assert before.selected is None
    assert after.selected.uid == (0, 1, 'backend')
    assert after.ifu_resolve.uid == (0, 1, 'ifu')


def test_matched_ahead_does_not_duplicate_its_source_after_the_accepting_edge():
    model = RedirectSchedule()
    model.advance(FtqInput(ahead=(1, 63)), 0, 1, [None] * 64)
    frame = FtqInput(backend_redirect=BackendRedirect(63, flag=1))
    before = model.advance(frame, 0, 2, [None] * 64)
    assert before.ahead_match and before.selected.uid == (0, 2, 'backend')
    assert model.view(frame, 0, 2).selected is None


def test_ifu_ras_target_is_captured_from_the_input_time_image_not_later_storage():
    model = RedirectSchedule()
    metadata = [None] * 64
    metadata[1] = {'redirectMeta_ras_topRetAddr_addr': 17}
    frame = FtqInput(ifu_redirect=IfuRedirect(1, ras_action=1))
    model.advance(frame, 0, 1, metadata)
    metadata[1] = {'redirectMeta_ras_topRetAddr_addr': 99}
    assert model.view(FtqInput(), 0, 2).selected.target == 17


def test_training_queue_cache_and_consume_are_three_distinct_stages():
    model, receiver = TrainingPath(), RedirectSchedule()
    metadata = [None] * 64
    frame = FtqInput(resolve=(ResolveReport(1, 0x100, 1, 0x900), None, None))
    view = receiver.view(frame, 0, 1)
    reports = model.reports(frame, view, 0, 1)
    model.advance(frame, reports, view, None, metadata, 2)
    assert model.cache is None and len(model.audit()) == 1
    idle = FtqInput()
    model.advance(idle, (), receiver.view(idle, 0, 2), None, metadata, 4)
    assert not model.queue and model.cache.value.start_pc == 0x100
    assert len(model.audit()) == 1 and not model.terminals
    consume = FtqInput(consumers=Consumers(train=1))
    model.advance(consume, (), receiver.view(consume, 0, 3), None, metadata, 6)
    assert not model.audit() and model.terminals[reports[0].uid] == ('completed', 6)


def test_first_mispredict_mask_follows_position_not_source_lane():
    model, receiver = TrainingPath(), RedirectSchedule()
    frame = FtqInput(resolve=tuple(ResolveReport(1, 0x100, offset, 0x900,
        mispredict=int(offset == 7)) for offset in (7, 2, 9)))
    reports = model.reports(frame, receiver.view(frame, 0, 1), 0, 1)
    model.advance(frame, reports, receiver.view(frame, 0, 1), None, [None] * 64, 2)
    model.advance(FtqInput(), (), receiver.view(FtqInput(), 0, 2), None, [None] * 64, 4)
    assert model.cache.value.branch_mask == 0b011
    assert [branch.position for branch in model.cache.value.branches] == [7, 2]
    assert model.terminals[reports[2].uid] == ('masked-after-mispredict', 4)
    assert len(model.audit()) == 2


@pytest.mark.parametrize('channel', ('backend', 'prefetch', 'fetch', 'training', 'redirect'))
async def test_wrong_public_payload_fails_the_automatic_top_path(ftq_factory, monkeypatch, channel):
    with pytest.raises(ScoreboardMismatch, match='ftq.frontend-transactions mismatch'):
        async with ftq_factory() as agent:
            await agent.allocate(tuple(PredictionSpec(0x80001000 + index * 32) for index in range(3)))
            monitor = {'backend': agent.private_monitor, 'prefetch': agent.prefetch_monitor,
                'fetch': agent.fetch_monitor, 'training': agent.training_monitor,
                'redirect': agent.redirect_monitor}[channel]
            capture = monitor.sample_fn

            def wrong(dut):
                value = capture(dut)
                if value is None:
                    return value
                if channel == 'backend':
                    return replace(value, wen=False)
                if channel in ('prefetch', 'fetch'):
                    return replace(value, index=value.index ^ 1)
                if channel == 'training':
                    return replace(value, start_pc=value.start_pc ^ 16)
                return replace(value, target=value.target ^ 16)

            monkeypatch.setattr(monitor, 'sample_fn', wrong)
            if channel == 'backend':
                await agent.predict(Prediction(0x80002000))
            elif channel in ('prefetch', 'fetch'):
                await agent.step(1)
            elif channel == 'training':
                await agent.resolve((ResolveReport(1, pc=0x80001020, offset=1,
                    target=0x90000000, mispredict=0),))
                await agent.step(4)
            else:
                await agent.backend_redirect(BackendRedirect(1, offset=0))


async def test_backpressured_prediction_retains_one_uid_until_acceptance(ftq_agent):
    agent = ftq_agent
    await agent.allocate(tuple(PredictionSpec(0x80001000 + index * 32) for index in range(32)), with_meta=False)
    await agent.offer(Prediction(0x80003000))
    await agent.step(3)
    receipt = agent.receipt()['frontend']
    candidate = receipt['pending_offer']
    assert candidate is not None and len(receipt['predictions']) == 33
    assert len(agent.frontend.attempts[candidate]) == 3
    await agent.consumers(prefetch=1, mainpipe=1)
    await agent.step(2)
    await agent.complete_offer()
    receipt = agent.receipt()['frontend']
    assert receipt['pending_offer'] is None and candidate in receipt['installed']
    assert len(receipt['predictions']) == 33
    assert len(agent.frontend.attempts[candidate]) == 5


async def test_swallowed_frontend_error_cannot_be_reset_or_finished_cleanly(ftq_factory, monkeypatch):
    with pytest.raises(RuntimeError, match='unreconciled'):
        async with ftq_factory() as agent:
            capture = agent.private_monitor.sample_fn
            monkeypatch.setattr(agent.private_monitor, 'sample_fn',
                lambda dut: replace(capture(dut), wen=False))
            with pytest.raises(AssertionError):
                await agent.predict(Prediction(0x80001000))
            monkeypatch.setattr(agent.private_monitor, 'sample_fn', capture)
            with pytest.raises(RuntimeError, match='unreconciled'):
                await agent.reset()


async def test_finish_cannot_invent_ready_for_accepted_training(ftq_factory):
    with pytest.raises(AssertionError, match='explicitly drain training'):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000),))
            await agent.resolve((ResolveReport(0, 0x80001000, 1, 0x90000000),))


async def test_explicit_training_drain_completes_the_original_report_uid(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000),))
    await agent.resolve((ResolveReport(0, 0x80001000, 1, 0x90000000),))
    offered = agent.receipt()['frontend']['resolve_offered']
    assert len(offered) == 1
    await agent.drain_training()
    receipt = agent.receipt()['frontend']
    assert not receipt['pending_reports']
    assert dict(receipt['resolve_done'])[offered[0]][0] == 'completed'
