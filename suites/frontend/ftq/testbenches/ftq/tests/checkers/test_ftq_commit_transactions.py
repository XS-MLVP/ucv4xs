"""TOP-014 automatic comparison and lifecycle controls; all are selftests."""
from dataclasses import replace

import pytest

from suites.frontend.ftq.testbenches.ftq.checker.commit import FtqCommits
from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput
from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import CommitEvent
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import PredictionSpec
from suites.frontend.ftq.testbenches.ftq.model import CallRet

pytestmark = pytest.mark.selftest


def frame(*rows, **values):
    return FtqInput(callret=rows + (None,) * (8 - len(rows)), **values)


def test_equal_callrets_have_distinct_completion_identity_and_input_meta_ancestor():
    checker = FtqCommits()
    checker.advance_slot(FtqInput(meta=Meta(2, fields={'commitMeta_ras_ssp': 7})), 1, None, None, 2)
    expected = CommitEvent(3, 7, 0, 0)
    checker.advance_slot(frame(CallRet(2, 3), CallRet(2, 3)), 2, None, expected, 4)
    assert len(checker.offered) == len(checker.accepted) == 2
    assert not checker.terminals
    checker.advance_slot(FtqInput(), 3, expected, expected, 6)
    checker.advance_slot(FtqInput(), 4, expected, None, 8)
    receipt = checker.receipt()
    assert not receipt['pending']
    assert [item.action.uid for item in receipt['terminals']] == [(0, 2, 0), (0, 2, 1)]
    assert [uid for _, uid in receipt['response_meta']] == [(0, 1, 'meta')] * 2


def test_reset_cancels_exact_old_epoch_and_does_not_invent_metadata_reset_value():
    checker = FtqCommits()
    checker.advance_slot(FtqInput(meta=Meta(2, fields={'commitMeta_ras_ssp': 7})), 1, None, None, 2)
    expected = CommitEvent(2, 7, 0, 0)
    checker.advance_slot(frame(CallRet(2, 2)), 2, None, expected, 4)
    checker.advance_slot(FtqInput(reset=True), 3, None, None, 6)
    checker.advance_slot(FtqInput(reset=True), 4, None, None, 8)
    checker.advance_slot(frame(CallRet(2, 2)), 5, None, expected, 10)
    checker.advance_slot(FtqInput(), 6, expected, None, 12)
    receipt = checker.receipt()
    assert [(item.action.uid, item.status) for item in receipt['terminals']] == [
        ((0, 2, 0), 'reset-cancelled'), ((1, 5, 0), 'completed')]
    assert receipt['response_meta'] == (((1, 5, 0), (0, 1, 'meta')),)


@pytest.mark.parametrize('mutation', ('missing', 'ras', 'metadata'))
def test_wrong_public_response_fails_the_projected_queue_path(mutation):
    checker = FtqCommits()
    checker.advance_slot(FtqInput(meta=Meta(2, fields={'commitMeta_ras_ssp': 7})), 1, None, None, 2)
    wrong = None if mutation == 'missing' else CommitEvent(3 if mutation == 'ras' else 2,
        8 if mutation == 'metadata' else 7, 0, 0)
    with pytest.raises(AssertionError):
        checker.advance_slot(frame(CallRet(2, 2)), 2, None, wrong, 4)
    with pytest.raises(RuntimeError, match='prior comparison'):
        checker.receipt()


def test_metadata_written_on_the_edge_is_not_used_for_the_old_completed_head():
    checker = FtqCommits()
    checker.advance_slot(FtqInput(meta=Meta(2, fields={'commitMeta_ras_ssp': 7})), 1, None, None, 2)
    checker.advance_slot(frame(CallRet(2, 2), CallRet(2, 2)), 2, None, CommitEvent(2, 7, 0, 0), 4)
    checker.advance_slot(FtqInput(meta=Meta(2, fields={'commitMeta_ras_ssp': 9})), 3,
        CommitEvent(2, 7, 0, 0), CommitEvent(2, 9, 0, 0), 6)
    checker.advance_slot(FtqInput(), 4, CommitEvent(2, 9, 0, 0), None, 8)
    assert checker.receipt()['response_meta'] == (
        ((0, 2, 0), (0, 1, 'meta')), ((0, 2, 1), (0, 3, 'meta')))


def test_reset_does_not_hide_a_real_metadata_write_from_the_input_owned_image():
    checker = FtqCommits()
    checker.advance_slot(FtqInput(reset=True, meta=Meta(0,
        fields={'commitMeta_ras_ssp': 7})), 1, None, None, 2)
    receipt = checker.receipt()
    assert len(receipt['metadata']) == 1
    assert checker.metadata[0].payload == (7, 0, 0)


@pytest.mark.parametrize('mutation', ('pending', 'accepted', 'terminal', 'response-meta'))
def test_erased_or_invented_lifecycle_evidence_cannot_be_reported_as_closure(mutation):
    checker = FtqCommits()
    checker.advance_slot(frame(CallRet(2, 2)), 1, None, CommitEvent(2, 0, 0, 0), 2)
    if mutation == 'pending':
        checker.pending.clear()
    elif mutation == 'accepted':
        checker.accepted.clear()
    elif mutation == 'terminal':
        checker.terminal(checker.pending[0], 'completed', 2)
    else:
        checker.response_meta[checker.pending[0].uid] = None
    with pytest.raises(AssertionError):
        checker.receipt()
    with pytest.raises(RuntimeError, match='ledger failure'):
        checker.receipt()


async def test_equal_visible_commits_complete_once_each_not_at_their_preview(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),))
    await agent.callret_rows((CallRet(0, 3), CallRet(0, 3)) + (None,) * 6)
    receipt = agent.receipt()['commits']
    assert len(receipt['accepted']) == len(receipt['pending']) == 2
    assert not receipt['terminals']
    assert agent.commit_event() == CommitEvent(3, 7, 0, 0)
    await agent.step(1)
    receipt = agent.receipt()['commits']
    assert len(receipt['terminals']) == len(receipt['pending']) == 1
    assert agent.commit_event() == CommitEvent(3, 7, 0, 0)
    await agent.step(1)
    receipt = agent.receipt()['commits']
    assert not receipt['pending'] and len(receipt['terminals']) == 2
    assert all(terminal.status == 'completed' for terminal in receipt['terminals'])
    assert len(set(receipt['accepted'])) == 2
    assert len({meta for _, meta in receipt['response_meta']}) == 1
    assert not receipt['unknown_metadata']


async def test_valid_only_held_lane_is_three_input_offers_not_one(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000),))
    await agent.cycle(frame(CallRet(0, 2)))
    await agent.step(2)
    await agent.release_callret()
    receipt = agent.receipt()['commits']
    assert len(receipt['offered']) == len(receipt['accepted']) == 3
    assert len(receipt['terminals']) == 2 and len(receipt['pending']) == 1
    assert len({uid[1] for uid in receipt['offered']}) == 3
    await agent.finish()
    assert not agent.receipt()['commits']['pending']


async def test_reset_records_cancelled_ancestry_before_reusing_equal_payload(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),))
    await agent.callret_rows((CallRet(0, 2),) * 3 + (None,) * 5)
    old = set(agent.receipt()['commits']['pending'])
    await agent.reset()
    receipt = agent.receipt()['commits']
    assert {terminal.action.uid for terminal in receipt['terminals']
            if terminal.status == 'reset-cancelled'} == old
    assert not receipt['pending']
    # The metadata storage itself is not reset. New epoch is a fresh FIFO UID;
    # the input-owned retained metadata is not relabelled as a reset value.
    await agent.allocate((PredictionSpec(0x80002000, meta={'commitMeta_ras_ssp': 9}),))
    await agent.callret(0, CallRet(0, 2))
    new = set(agent.receipt()['commits']['pending'])
    assert len(new) == 1 and not (old & new)
    assert agent.commit_event().meta_ssp == 9
    await agent.finish()
    assert {terminal.action.uid for terminal in agent.receipt()['commits']['terminals']
            if terminal.status == 'completed'} == new


async def test_none_and_preedge_guard_rejections_are_not_silently_counted_as_accepts(ftq_agent):
    agent = ftq_agent
    await agent.allocate(tuple(PredictionSpec(0x80000000 + index * 32,
        meta={'commitMeta_ras_ssp': index % 16}) for index in range(64)), consume=True)
    await agent.callret(0, CallRet(0, 0))
    assert not agent.receipt()['commits']['accepted']
    assert agent.receipt()['commits']['terminals'][0].status == 'filtered-none'
    for _ in range(20):
        await agent.callret_rows(tuple(CallRet(lane, lane % 3 + 1) for lane in range(8)))
    receipt = agent.receipt()['commits']
    assert any(terminal.status == 'capacity-rejected' for terminal in receipt['terminals'])
    assert len(receipt['offered']) == 161
    await agent.finish()
    receipt = agent.receipt()['commits']
    assert not receipt['pending']
    assert {terminal.action.uid for terminal in receipt['terminals'] if terminal.status == 'completed'} == set(receipt['accepted'])


@pytest.mark.parametrize('mutation', ('missing', 'ras', 'meta_ssp', 'meta_tosw_flag', 'meta_tosw_value'))
async def test_corrupted_bpu_commit_fails_without_manual_test_assertions(ftq_factory, monkeypatch, mutation):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),))
            capture = agent.commit_monitor.sample_fn

            def wrong(dut):
                value = capture(dut)
                if value is None:
                    return None
                if mutation == 'missing':
                    return None
                key = 'ras_action' if mutation == 'ras' else mutation
                return replace(value, **{key: getattr(value, key) ^ 1})

            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', wrong)
            await agent.callret(0, CallRet(0, 2))


async def test_wrong_entry_metadata_is_rejected_even_with_equal_ras_action(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),
                                  PredictionSpec(0x80001020, meta={'commitMeta_ras_ssp': 9})))
            capture = agent.commit_monitor.sample_fn

            def wrong(dut):
                value = capture(dut)
                return None if value is None else replace(value, meta_ssp=9)

            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', wrong)
            await agent.callret(0, CallRet(0, 2))


async def test_same_ssp_cannot_hide_a_wrong_metadata_owner_in_the_tosw_fields(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000, meta={
                'commitMeta_ras_ssp': 7, 'commitMeta_ras_tosw_value': 5}),
                PredictionSpec(0x80001020, meta={
                'commitMeta_ras_ssp': 7, 'commitMeta_ras_tosw_value': 9})))
            capture = agent.commit_monitor.sample_fn

            def wrong(dut):
                value = capture(dut)
                return None if value is None else replace(value, meta_tosw_value=9)

            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', wrong)
            await agent.callret(0, CallRet(0, 2))


async def test_native_reset_slot_meta_write_is_retained_with_its_actual_input_ancestor(ftq_agent):
    agent = ftq_agent
    # Explicit port-domain reset pressure, not a claim BPU emits valid in reset.
    await agent.cycle(FtqInput(reset=True, meta=Meta(0, fields={'commitMeta_ras_ssp': 7})))
    writes = agent.receipt()['commits']['metadata']
    assert len(writes) == 1
    await agent.cycle(FtqInput())
    await agent.allocate((PredictionSpec(0x80001000),), with_meta=False)
    await agent.callret(0, CallRet(0, 2))
    assert agent.commit_event() == CommitEvent(2, 7, 0, 0)
    await agent.finish()
    receipt = agent.receipt()['commits']
    assert receipt['response_meta'] == ((receipt['accepted'][0], writes[0].uid),)
    assert not receipt['unknown_metadata']


async def test_backend_redirect_does_not_cancel_retired_callret_actions(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),))
    await agent.cycle(frame(CallRet(0, 2), CallRet(0, 3),
        backend_redirect=BackendRedirect(0, offset=0)))
    accepted = set(agent.receipt()['commits']['accepted'])
    await agent.cycle(FtqInput())
    assert agent.commit_event().ras_action == 3
    await agent.finish()
    receipt = agent.receipt()['commits']
    assert {terminal.action.uid for terminal in receipt['terminals'] if terminal.status == 'completed'} == accepted
    assert all(terminal.status == 'completed' for terminal in receipt['terminals'])


async def test_native_old_head_uses_preedge_metadata_and_new_preview_uses_postedge_write(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x80001000, meta={'commitMeta_ras_ssp': 7}),))
    await agent.callret_rows((CallRet(0, 2),) * 2 + (None,) * 6)
    old_meta = agent.receipt()['commits']['metadata'][-1].uid
    # Explicit same-index metadata port pressure, not a second BPU s3 retirement.
    await agent.cycle(FtqInput(meta=Meta(0, fields={'commitMeta_ras_ssp': 9})))
    receipt = agent.receipt()['commits']
    new_meta = receipt['metadata'][-1].uid
    assert receipt['response_meta'][0][1] == old_meta
    assert agent.commit_event().meta_ssp == 9
    await agent.cycle(FtqInput())
    await agent.finish()
    assert [uid for _, uid in agent.receipt()['commits']['response_meta']] == [old_meta, new_meta]


async def test_finish_checks_the_autonomous_last_response_without_inventing_inputs(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000),))
            await agent.callret(0, CallRet(0, 2))
            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', lambda _: None)
            await agent.finish()


async def test_second_idle_tail_cannot_hide_a_spurious_commit_after_a_correct_first_tail(ftq_factory, monkeypatch):
    with pytest.raises(AssertionError):
        async with ftq_factory() as agent:
            captures = 0
            capture = agent.commit_monitor.sample_fn

            def wrong(dut):
                nonlocal captures
                captures += 1
                value = capture(dut)
                return CommitEvent(2, 0, 0, 0) if captures == 4 else value

            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', wrong)
            await agent.finish()


async def test_swallowed_automatic_mismatch_is_sticky_at_reset_and_normal_fixture_finish(ftq_factory, monkeypatch):
    with pytest.raises(RuntimeError, match='unreconciled'):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000),))
            capture = agent.commit_monitor.sample_fn
            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', lambda _: None)
            with pytest.raises(AssertionError):
                await agent.callret(0, CallRet(0, 2))
            monkeypatch.setattr(agent.commit_monitor, 'sample_fn', capture)
            with pytest.raises(RuntimeError, match='unreconciled'):
                await agent.reset()


async def test_swallowed_public_checker_error_is_sticky_without_any_hardware_work(ftq_factory):
    with pytest.raises(RuntimeError, match='prior comparison'):
        async with ftq_factory() as agent:
            with pytest.raises(AssertionError):
                agent.commit_checker.check(CallRet(0, 2), CallRet(1, 2))


async def test_finish_budget_cannot_become_success_by_discarding_pending_uids(ftq_factory):
    with pytest.raises(AssertionError, match='finish budget'):
        async with ftq_factory() as agent:
            await agent.allocate((PredictionSpec(0x80001000),))
            await agent.callret_rows((CallRet(0, 2),) * 8)
            accepted = set(agent.receipt()['commits']['accepted'])
            try:
                await agent.finish(cycles=2)
            except AssertionError:
                assert len(agent.commit_checker.pending) == 6
                assert set(agent.commit_checker.accepted) == accepted
                raise


async def test_uninitialized_meta_is_explicit_unknown_not_a_zero_or_identity_match(ftq_agent):
    agent = ftq_agent
    await agent.callret(0, CallRet(63, 2))
    await agent.finish()
    receipt = agent.receipt()['commits']
    assert receipt['unknown_metadata'] == receipt['accepted']
    assert receipt['response_meta'] == ((receipt['accepted'][0], None),)


@pytest.mark.parametrize('bad', (True, 0, 1, -1, 1.5))
async def test_invalid_finish_budget_leaves_uid_and_clock_unchanged(ftq_agent, bad):
    agent = ftq_agent
    count = agent.dut.sampled_cycles
    receipt = agent.receipt()
    with pytest.raises(ValueError, match='at least two'):
        await agent.finish(cycles=bad)
    assert agent.dut.sampled_cycles == count and agent.receipt() == receipt
