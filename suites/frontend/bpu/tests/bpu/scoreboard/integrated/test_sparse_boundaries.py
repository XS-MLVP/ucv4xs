"""Drain-aware boundary steering uses model writes, never DUT chosen data."""
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch

from bpuverify.bpu.case.bypass.sparse_wrap import check_sparse_wrap
from bpuverify.bpu.env.bypass.sparse import SparseProgramEnvironment
from bpuverify.bpu.model.bypass.model import BypassReference
from tests.bpu.scoreboard.integrated.test_partial_wrap_preparation import allocate


class BoundaryHarness(SparseProgramEnvironment):
    def __init__(self, initial, retirements):
        self.upper = BypassReference(1)
        self.steps = 0
        for _ in range(8 + initial):
            self.advance()
        self.retirements = iter(retirements)
        self.board = Scoreboard('sparse-boundary-contract')
        self.ready_calls, self.stop_calls = [], 0
        checker = SimpleNamespace(bypass=SimpleNamespace(references=[None, self.upper],
            last_event=SimpleNamespace(tick=0)), compare=self.compare)
        super().__init__(SimpleNamespace(set_ready=self.ready), checker, None, {})

    def advance(self):
        allocate(self.upper, 265, 75)
        self.steps += 1

    def compare(self, expected, actual, **context):
        self.board.check(expected=expected, actual=actual)

    async def ready(self, **values):
        self.ready_calls.append(values)

    async def wait(self, operation, *args):
        return await operation

    async def until(self, predicate, label):
        for _ in range(16):
            if predicate():
                return
            self.advance()
        raise AssertionError(label)

    async def stop(self, label):
        self.stop_calls += 1
        for _ in range(next(self.retirements)):
            self.advance()
        self.checker.bypass.last_event.tick = self.steps * 2


@pytest.mark.parametrize('target', (4, 5, 6))
@pytest.mark.parametrize('retired', (0, 1, 2))
async def test_boundary_accounts_for_all_retiring_model_writes(target, retired):
    env = BoundaryHarness(7, (retired,) * 8)
    await env.align_upper_boundary(target, env.until)
    assert env.upper.enq % 8 == target
    assert env.stop_calls == (1 if retired == 0 else 2)
    assert all(row['accepted_writes_retired'] == retired for row in env.report['boundary_alignment'])
    if retired:
        assert env.report['boundary_alignment'][1]['stop_slot'] == (target - retired) % 8


async def test_already_drained_boundary_never_resumes_young_work():
    env = BoundaryHarness(7, ())
    before = env.upper.state()
    await env.align_upper_boundary(7, env.until)
    assert env.upper.state() == before
    assert not env.ready_calls and not env.stop_calls and not env.report


async def test_retirement_can_change_without_using_a_fixed_latency():
    env = BoundaryHarness(7, (1, 2, 2))
    await env.align_upper_boundary(5, env.until)
    assert env.upper.enq % 8 == 5
    assert [row['accepted_writes_retired'] for row in env.report['boundary_alignment']] == [1, 2, 2]


async def test_nonconvergent_retirement_must_fail_not_credit_a_different_boundary():
    env = BoundaryHarness(7, (1, 2) * 4)
    with pytest.raises(ScoreboardMismatch, match='expected 5'):
        await env.align_upper_boundary(5, env.until)
    assert env.stop_calls == 8


async def test_history_progress_failure_is_not_suppressed():
    env = BoundaryHarness(7, (1,) * 8)
    async def failed(predicate, label):
        raise RuntimeError('no recurrent input history')
    with pytest.raises(RuntimeError, match='no recurrent input history'):
        await env.align_upper_boundary(5, failed)
    assert not env.stop_calls


@pytest.mark.parametrize('slot', (0, 2, 7, True, None, '5', 4.0))
async def test_invalid_wrap_request_fails_before_any_agent_or_output_access(slot):
    with pytest.raises(ValueError, match='survivor'):
        await check_sparse_wrap(None, None, survivor_slot=slot)
