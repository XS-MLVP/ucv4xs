"""Input identity/phase/termination controls; native injections are selftests."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.ftq.testbenches.ftq.checker.frontend import FtqFrontend
from suites.frontend.ftq.testbenches.ftq.checker.handoffs import RequestHandoffs
from suites.frontend.ftq.testbenches.ftq.checker.handoffs import RobTargets
from suites.frontend.ftq.testbenches.ftq.checker.model import FtqChecker
from suites.frontend.ftq.testbenches.ftq.checker.requests import distance_bits
from suites.frontend.ftq.testbenches.ftq.checker.requests import fetch_size
from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput
from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Consumers
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.ftq.transactions.types import PredictionSpec
from suites.frontend.ftq.testbenches.ftq.transactions.types import TrainingEntry
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import Branch

pytestmark = pytest.mark.selftest


def entry(identity, uid, allocation=None):
    return SimpleNamespace(identity=identity, uid=uid, allocation=uid if allocation is None else allocation)


def requests(first, second=None):
    return {name: (first is not None, bool(second), 0, (first, second), ()) for name in ('prefetch', 'fetch')}


def test_handoff_subset_and_retry_root_are_not_guessed_from_payload():
    model = RequestHandoffs()
    first, second = entry(0, (1, 1, 1)), entry(1, (1, 2, 2))
    info = requests(first, second)
    model.sync(info, 1, 2)
    model.sync(info, 1, 4)
    assert len(model.offered) == 2 and not model.accepted
    model.consume(FtqInput(consumers=Consumers(prefetch=1, mainpipe=1)), info, 6)
    assert model.handoffs == [('prefetch', first.uid, 6), ('prefetch', second.uid, 6), ('fetch', first.uid, 6)]
    model.sync(requests(entry(0, (1, 3, 3), allocation=first.uid)), 1, 6)
    for attempt in model.current.values():
        assert attempt.retry_of is not None
        assert model.offered[attempt.retry_of].primary == first.uid
    assert len(model.audit()) == 2


def test_reset_cancelled_offer_is_not_accepted_or_completed():
    model = RequestHandoffs()
    model.sync(requests(entry(0, (1, 1, 1))), 1, 2)
    model.sync(requests(None), 2, 4, reason='reset-cancelled-offer')
    assert not model.audit() and not model.accepted
    assert {status for status, _ in model.terminals.values()} == {'reset-cancelled-offer'}


@pytest.mark.parametrize('mutation', ('handoffs', 'accepted', 'offered', 'terminal'))
def test_erasing_handoff_evidence_is_detected(mutation):
    model = RequestHandoffs()
    info = requests(entry(0, (1, 1, 1)))
    model.sync(info, 1, 2)
    model.consume(FtqInput(consumers=Consumers(prefetch=1, mainpipe=1)), info, 4)
    getattr(model, 'terminals' if mutation == 'terminal' else mutation).clear()
    with pytest.raises(AssertionError):
        model.audit()


def test_repeated_rob_targets_do_not_repeat_retirement_and_full_laps_remain_legal():
    model = RobTargets()
    for index in range(256):
        pointer = index % 128
        model.advance(FtqInput(commit=(pointer // 64, pointer % 64)), 1, index + 1,
            pointer, pointer, [None] * 64, 2 * index + 2)
    model.advance(FtqInput(commit=(1, 63)), 1, 257, 0, 127, [None] * 64, 514)
    assert not model.audit() and len(model.retired) == 256
    assert model.terminals[(1, 257, 'rob-commit')][0] == 'duplicate-old-target'


@pytest.mark.parametrize('left,right,expected', ((0, 1, 63), (0, 2, 62), (64, 0, 64), (65, 63, 2), (3, 1, 2)))
def test_fixed_width_backwards_distance_is_characterization_not_signed_queue_age(left, right, expected):
    assert distance_bits(left, right) == expected


def test_invalid_negative_fetch_extent_is_not_implicitly_python_signed():
    assert fetch_size(15, 0) == 50
    assert fetch_size(15, 15) == 1


def test_mask_invariant_uses_program_position_not_compressed_lane_order():
    value = TrainingEntry(0, (), (Branch(7, 0, 1, 1, 1, 0), Branch(2, 0, 1, 0, 1, 0)), 0, 0, 0)
    assert FtqChecker.training_mask_ok(value)
    assert not FtqChecker.training_mask_ok(replace(value,
        branches=value.branches + (Branch(9, 0, 1, 0, 1, 0),)))


def test_swallowed_prediction_ledger_failure_remains_sticky():
    model = FtqFrontend()
    model.begin_slot(FtqInput(prediction=Prediction(0x100)), 1, 1)
    saved = model.candidate
    model.candidate = None
    with pytest.raises(AssertionError, match='ancestry'):
        model.audit()
    model.candidate = saved
    with pytest.raises(RuntimeError, match='failure'):
        model.require_clean()


def test_plan_withdrawal_is_recorded_without_an_invented_acceptance_edge():
    model = FtqFrontend()
    model.present(FtqInput(prediction=Prediction(0x100)), 1)
    original = model.candidate
    model.present(FtqInput(), 2)
    assert model.candidate is None
    assert model.prediction_done[original] == 'withdrawn-before-acceptance'
    assert not model.installed and not model.audit()


async def test_held_equal_predictions_are_distinct_only_after_each_real_acceptance(ftq_agent):
    agent = ftq_agent
    value = Prediction(0x80001000)
    await agent.offer(value)
    await agent.step(3)
    await agent.complete_offer()
    receipt = agent.receipt()['frontend']
    assert len(receipt['predictions']) == len(set(receipt['installed'])) == 3
    assert len({item.allocation for item in agent.frontend.installed.values()}) == 3
    assert {item.prediction for item in agent.frontend.installed.values()} == {value}
    assert all(status == 'installed' for _, status in receipt['prediction_done'])


async def test_unaccepted_offer_can_be_withdrawn_without_making_up_a_response(ftq_agent):
    agent = ftq_agent
    await agent.allocate(tuple(PredictionSpec(0x80001000 + index * 32) for index in range(32)), with_meta=False)
    await agent.offer(Prediction(0x80003000))
    await agent.step(2)
    candidate = agent.receipt()['frontend']['pending_offer']
    await agent.complete_offer()
    receipt = agent.receipt()['frontend']
    assert receipt['pending_offer'] is None and candidate not in receipt['installed']
    assert dict(receipt['prediction_done'])[candidate] == 'withdrawn-before-acceptance'


async def test_override_at_ready_zero_revises_one_input_allocation_and_links_request_retry(ftq_agent):
    agent = ftq_agent
    await agent.allocate(tuple(PredictionSpec(0x80001000 + index * 32) for index in range(32)), with_meta=False)
    assert not agent.prediction_ready()
    original = agent.frontend.entries[0]
    await agent.override(Prediction(0x80003000, s3_override=1, s3_ptr=0))
    revision = agent.frontend.entries[0]
    assert revision.uid != original.uid and revision.parent == original.uid
    assert revision.allocation == original.allocation
    requests = agent.receipt()['frontend']['requests']
    retries = [attempt for attempt in requests['offered'] if attempt.primary == revision.uid]
    assert {attempt.channel for attempt in retries} == {'prefetch', 'fetch'}
    assert all(attempt.retry_of is not None and attempt.allocation == original.allocation for attempt in retries)
    assert not requests['accepted']


async def test_reset_cancelled_offer_and_fresh_equal_payload_never_share_a_retry_root(ftq_agent):
    agent = ftq_agent
    await agent.predict(Prediction(0x80001000))
    original = agent.frontend.entries[0]
    await agent.reset()
    await agent.predict(Prediction(0x80001000))
    fresh = agent.frontend.entries[0]
    assert fresh.allocation != original.allocation
    receipts = agent.receipt()['frontend']['requests']
    assert any(status == 'reset-cancelled-offer' for _, (status, _) in receipts['terminals'])
    assert all(attempt.retry_of is None for attempt in receipts['offered'] if attempt.primary == fresh.uid)


async def test_backend_arbitration_does_not_erase_an_already_registered_ifu_resolve(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x1000, meta={'redirectMeta_ras_topRetAddr_addr': 0x1234}),
                          PredictionSpec(0x1020), PredictionSpec(0x1040)))
    await agent.cycle(FtqInput(backend_redirect=BackendRedirect(1, offset=0),
        ifu_redirect=IfuRedirect(0, pc=0x2000, offset=1, ras_action=1)))
    await agent.cycle(FtqInput())
    await agent.drain_training()
    receipt = agent.receipt()['frontend']
    events = receipt['receivers']['offered']
    ifu = next(event for event in events if event.source == 'ifu')
    assert ifu.target == 0x1234 and ifu.target_meta_uid is not None
    assert dict(receipt['receivers']['redirects'])[ifu.uid][0] == 'backend-arbitration-cancelled'
    assert dict(receipt['receivers']['resolves'])[ifu.uid][0] == 'forwarded-to-resolve'
    child = dict(receipt['receivers']['resolve_children'])[ifu.uid]
    assert dict(receipt['resolve_done'])[child][0] == 'completed'


async def test_matched_ahead_metadata_read_has_the_old_input_ancestor_on_a_write_edge(ftq_agent):
    agent = ftq_agent
    # Seed the no-reset store during reset, not by sending an illegal second
    # s3 update for an entry that has already passed PNR.
    await agent.cycle(FtqInput(reset=True, meta=Meta(1, fields={'redirectMeta_commonHRMeta_ghr': 7})))
    await agent.reset()
    await agent.allocate((PredictionSpec(0x1000), PredictionSpec(0x1020)), meta_limit=1)
    original = agent.frontend.meta_uids[1]
    await agent.ahead_set(1)
    await agent.ahead_clear()
    await agent.cycle(FtqInput(backend_redirect=BackendRedirect(1, offset=1),
        meta=Meta(1, fields={'redirectMeta_commonHRMeta_ghr': 9})))
    await agent.cycle(FtqInput())
    written = agent.frontend.meta_uids[1]
    assert written != original
    await agent.backend_redirect(BackendRedirect(1, offset=1))
    associations = agent.receipt()['frontend']['receivers']['response_meta']
    assert [ancestor for _, ancestor in associations] == [original, written]


async def test_finish_observes_the_second_empty_frontend_tail_slot(ftq_factory, monkeypatch):
    with pytest.raises(ScoreboardMismatch, match='ftq.frontend-transactions mismatch'):
        async with ftq_factory() as agent:
            capture = agent.private_monitor.sample_fn
            start = agent._slot

            def late(dut):
                value = capture(dut)
                return replace(value, wen=True) if agent._slot == start + 2 else value

            monkeypatch.setattr(agent.private_monitor, 'sample_fn', late)


async def test_swallowed_handoff_audit_failure_cannot_be_repaired_into_a_clean_finish(ftq_factory):
    with pytest.raises(RuntimeError, match='prior comparison or lifecycle failure'):
        async with ftq_factory() as agent:
            await agent.predict(Prediction(0x1000))
            await agent.consumers(prefetch=1, mainpipe=1)
            await agent.step(1)
            saved = list(agent.frontend.requests.handoffs)
            agent.frontend.requests.handoffs.clear()
            with pytest.raises(AssertionError, match='handoff'):
                agent.receipt()
            agent.frontend.requests.handoffs[:] = saved


async def test_reset_cancels_ifu_resolve_but_checks_old_nonreset_redirect_transport(ftq_agent):
    agent = ftq_agent
    await agent.allocate((PredictionSpec(0x1000), PredictionSpec(0x1020), PredictionSpec(0x1040)))
    await agent.cycle(FtqInput(backend_redirect=BackendRedirect(1, offset=0),
                              ifu_redirect=IfuRedirect(0, pc=0x2000)))
    assert agent.redirect_event() is not None
    await agent.cycle(FtqInput(reset=True))
    await agent.cycle(FtqInput())
    receipt = agent.receipt()['frontend']
    events = receipt['receivers']['offered']
    backend = next(event for event in events if event.source == 'backend')
    ifu = next(event for event in events if event.source == 'ifu')
    assert dict(receipt['receivers']['redirects'])[backend.uid][0] == 'reset-suppressed-application'
    assert dict(receipt['receivers']['resolves'])[ifu.uid][0] == 'reset-cancelled'
    assert not receipt['resolve_offered'] and not receipt['redirect_edges']
    assert not receipt['receivers']['pending']
