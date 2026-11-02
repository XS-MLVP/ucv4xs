"""FTQ fixture completion policy; no native DUT or hardware credit."""
import asyncio
from types import SimpleNamespace

import pytest

from suites.frontend.ftq.fixtures import agent_runtime


class Agent:
    def __init__(self, *, unresolved=False, cleanup_error=False):
        self.unresolved, self.cleanup_error = unresolved, cleanup_error
        self.events = []

    async def start(self):
        self.events.append('start')

    async def finish(self):
        self.events.append('finish')
        if self.unresolved:
            raise RuntimeError('unreconciled input')

    async def aclose(self):
        self.events.append('cleanup')
        if self.cleanup_error:
            raise ValueError('independent cleanup failure')


def request(outcome, phase='call'):
    return SimpleNamespace(node=SimpleNamespace(_ftq_reports={phase: outcome} if outcome else {}))


@pytest.mark.parametrize('outcome', ('failed', 'skipped'))
@pytest.mark.parametrize('phase', ('setup', 'call'))
def test_nonpassing_report_is_not_duplicated_by_normal_finish(outcome, phase):
    async def run():
        agent = Agent(unresolved=True)
        async with agent_runtime(agent, request(outcome, phase)):
            pass
        assert agent.events == ['start', 'cleanup']
    asyncio.run(run())


@pytest.mark.parametrize('outcome', ('passed', None))
def test_passing_or_missing_report_cannot_hide_unreconciled_work(outcome):
    async def run():
        agent = Agent(unresolved=True)
        with pytest.raises(RuntimeError, match='unreconciled'):
            async with agent_runtime(agent, request(outcome)):
                pass
        assert agent.events == ['start', 'finish', 'cleanup']
    asyncio.run(run())


def test_clean_body_finishes_before_cleanup():
    async def run():
        agent = Agent()
        async with agent_runtime(agent, request('passed')):
            pass
        assert agent.events == ['start', 'finish', 'cleanup']
    asyncio.run(run())


def test_direct_body_exception_keeps_its_identity_without_fake_finish():
    async def run():
        agent = Agent(unresolved=True)
        error = LookupError('original body failure')
        with pytest.raises(LookupError) as caught:
            async with agent_runtime(agent):
                raise error
        assert caught.value is error and agent.events == ['start', 'cleanup']
    asyncio.run(run())


@pytest.mark.parametrize('outcome', ('failed', 'passed'))
def test_independent_cleanup_failure_always_propagates(outcome):
    async def run():
        agent = Agent(cleanup_error=True)
        with pytest.raises(ValueError, match='independent cleanup'):
            async with agent_runtime(agent, request(outcome)):
                pass
        assert agent.events[-1] == 'cleanup'
    asyncio.run(run())


@pytest.mark.parametrize('outcome', ('passed', None))
def test_clean_body_cannot_hide_prior_cycle_sampling_failure(outcome):
    async def run():
        agent = Agent()

        def sampling_audit():
            raise RuntimeError('unreconciled cycle sampling')

        agent.dut = SimpleNamespace(check_sampling=sampling_audit)
        with pytest.raises(RuntimeError, match='unreconciled cycle sampling'):
            async with agent_runtime(agent, request(outcome)):
                pass
        assert agent.events == ['start', 'finish', 'cleanup']
    asyncio.run(run())
