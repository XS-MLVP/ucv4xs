"""Positive/negative controls for owner APIs; not native hardware credit."""
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard, TransferState

from suites.frontend.bpu.testbenches.bpu.env.agent.main import BpuAgent
from suites.frontend.bpu.testbenches.bpu.tests.scenarios import composition
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBatchTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBranchFeedback
from suites.frontend.bpu.testbenches.ittage.env.agent.main import IttageAgent
from suites.frontend.bpu.testbenches.mbtb.env.agent.main import MbtbAgent
from suites.frontend.bpu.testbenches.sc.env.agent.main import ScAgent
from suites.frontend.bpu.testbenches.ubtb.env.agent.main import UbtbAgent
from suites.frontend.bpu.testbenches.uras.env.agent.main import UrasAgent
from suites.frontend.bpu.testbenches.utage.env.agent.main import UtageAgent

pytestmark = pytest.mark.selftest


def owner(cls):
    agent = cls.__new__(cls)
    agent._started, agent._finished, agent._execution = True, False, object()
    failure = []

    def raise_failure():
        if failure:
            raise failure[0]

    agent.reference = NS(board=Scoreboard('owner-api-control'), raise_failure=raise_failure)
    return agent, failure


@pytest.mark.parametrize('cls', (UbtbAgent, IttageAgent, UrasAgent, ScAgent))
def test_checking_snapshot_is_frozen_detached_and_never_hides_a_latched_error(cls):
    agent, failure = owner(cls)
    agent.reference.board.check(expected=7, actual=7)
    status = agent.checking_status()
    assert status.checked == status.passed == 1 and status.failed == 0
    agent.reference.board.check(expected=9, actual=9)
    assert status.checked == 1 and agent.checking_status().checked == 2
    with pytest.raises(FrozenInstanceError):
        status.checked = 100
    error = AssertionError('latched independent mismatch')
    failure.append(error)
    with pytest.raises(AssertionError) as caught:
        agent.checking_status()
    assert caught.value is error
    failure.clear()
    agent._started, agent._execution = False, None
    with pytest.raises(RuntimeError, match='active Execution'):
        agent.checking_status()


@pytest.mark.parametrize('reset,ready', ((0, 0), (0, 1), (1, 0), (1, 1)))
def test_reset_readiness_preserves_both_reported_values(reset, ready):
    agent, _ = owner(UbtbAgent)
    agent.ports = NS(status=NS(bits=NS(sample=lambda: NS(
        reset_done=NS(as_int=lambda: reset), train_ready=NS(as_int=lambda: ready)))))
    assert agent.readiness() == (bool(reset), bool(ready))


def test_learning_backlog_is_expected_obligations_not_mutable_model_or_actual_occupancy():
    agent, failure = owner(UtageAgent)
    updates = NS(outstanding=list(range(8)), pressured=True)
    agent.reference.model = NS(updates=(updates, NS(outstanding=[], pressured=False)))
    before = agent.learning_backlog(0)
    assert (before.outstanding, before.pressured) == (8, True)
    updates.outstanding.pop()
    assert before.outstanding == 8 and agent.learning_backlog(0).outstanding == 7
    with pytest.raises(FrozenInstanceError):
        before.pressured = False
    for table in (-1, 2, True, '0'):
        with pytest.raises(ValueError, match='table'):
            agent.learning_backlog(table)
    failure.append(AssertionError('reference failed'))
    with pytest.raises(AssertionError, match='reference failed'):
        agent.learning_backlog(0)


@pytest.mark.parametrize('failed_owner', ('reference', 'lookup_inputs', 'training_inputs'))
def test_learning_checkpoint_keeps_each_independent_sticky_error(failed_owner):
    agent, _ = owner(MbtbAgent)
    visited = []
    for name in ('reference', 'lookup_inputs', 'training_inputs'):
        def check(name=name):
            visited.append(name)
            if name == failed_owner:
                raise AssertionError(name)
        setattr(agent, name, NS(raise_failure=check))
    with pytest.raises(AssertionError, match=failed_owner):
        agent.check_learning()
    assert visited[-1] == failed_owner


def test_sc_history_coverage_checks_every_group_without_returning_it():
    agent, failure = owner(ScAgent)
    calls = []
    agent.semantic_coverage = NS(groups={name: NS(assert_coverage=lambda p, name=name:
        calls.append((name, p))) for name in ('valid', 'invalid')})
    assert agent.assert_history_coverage(100) is None
    assert calls == [('valid', 100), ('invalid', 100)]
    failure.append(AssertionError('SC learning mismatch'))
    with pytest.raises(AssertionError, match='SC learning mismatch'):
        agent.assert_history_coverage(100)
    assert len(calls) == 2


def test_feedback_submission_is_only_the_original_input_lease_not_a_commit():
    agent, _ = owner(BpuAgent)
    calls = []
    pending = NS(state=TransferState.PENDING, accepted_event=None)

    def send(request):
        calls.append(request)
        return pending

    agent.training_driver = NS(send=send)
    request = BpuBatchTraining(0x4000, {}, (BpuBranchFeedback(2, 0x5000, 2),))
    assert agent.submit_training_batch(request) is pending
    assert calls == [request]
    assert pending.state is TransferState.PENDING and pending.accepted_event is None
    with pytest.raises(TypeError, match='BpuBatchTraining'):
        agent.submit_training_batch(object())
    assert calls == [request]


@pytest.mark.asyncio
async def test_prediction_window_uses_accept_ticks_and_proves_the_end_cut():
    agent, _ = owner(BpuAgent)
    agent._phr_observation = None
    values = [NS(accepted_tick=tick, value=('prediction', tick)) for tick in (2, 4, 6, 8)]

    async def recv():
        return values.pop(0)

    agent.prediction_monitor = NS(recv=recv)
    window = await agent.prediction_window(2, 6)
    assert tuple(frame.accepted_tick for frame in window) == (4, 6)
    assert tuple(frame.prediction for frame in window) == (('prediction', 4), ('prediction', 6))
    assert not values  # The later accepted sample, not a fixed delay, proves end.
    with pytest.raises(FrozenInstanceError):
        window[0].accepted_tick = 0


@pytest.mark.asyncio
async def test_exhausted_or_wrong_owner_window_cannot_return_partial_success():
    agent, _ = owner(BpuAgent)
    agent._phr_observation = None

    async def recv():
        return NS(accepted_tick=4, value=0)

    agent.prediction_monitor = NS(recv=recv)
    with pytest.raises(AssertionError, match='did not reach'):
        await agent.prediction_window(2, 6, limit=2)
    for start, end in ((-1, 2), (8, 2), (False, 2)):
        with pytest.raises(ValueError, match='ticks'):
            await agent.prediction_window(start, end)
    agent._phr_observation = object()
    with pytest.raises(RuntimeError, match='owns the streams'):
        await agent.prediction_window(2, 6)


@pytest.mark.asyncio
@pytest.mark.parametrize('finish_fails', (False, True))
async def test_composition_report_is_detached_and_cannot_escape_failed_finish(monkeypatch, finish_fails):
    checks = []

    @asynccontextmanager
    async def program(agent, pc, scenario_checks, *, checker_factory):
        checker = checker_factory.__new__(checker_factory)
        checker.failure = None
        checker.both_compared = [dict(tick=4, ahead_hits=[1], main_hits=[1])]
        checker.counts = Counter(compared=1)
        checks.append(checker)
        yield NS(checker=checker)
        if finish_fails:
            raise AssertionError('undrained accepted work')

    async def discover(*args):
        pass

    monkeypatch.setattr(composition, 'early_direction_program', program)
    monkeypatch.setattr(composition, 'discover_negative_path', discover)
    if finish_fails:
        with pytest.raises(AssertionError, match='undrained'):
            await composition.early_composition(None, pc=0x40000000, probe='main-ahead')
    else:
        report = await composition.early_composition(None, pc=0x40000000, probe='main-ahead')
        assert set(report) == {'cycles', 'counts'}
        report['cycles'][0]['ahead_hits'][0] = 0
        assert checks[0].both_compared[0]['ahead_hits'] == [1]
    with pytest.raises(ValueError, match='unknown'):
        await composition.early_composition(None, pc=0x40000000, probe='ignore-failures')
