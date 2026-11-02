"""The IFU loader must honor the seed recorded by ucv, without opening a DUT."""
import sys
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from suites.frontend.ifu import harness
from suites.frontend.ifu import fixtures as harness_fixtures


@pytest.mark.parametrize('configured,override,expected', [('7', None, 7), ('7', 3, 3),
                                                       (None, None, 1)])
def test_ifu_native_arguments_use_recorded_seed(monkeypatch, configured, override, expected):
    class FakeDut:
        def __init__(self, arguments, **options):
            self.arguments, self.options, self.finished = arguments, options, False

        def Finish(self):
            self.finished = True

    FakeDut.__module__ = 'ifu_loader_seed_control'
    monkeypatch.setitem(sys.modules, FakeDut.__module__, SimpleNamespace(
        xsp=SimpleNamespace(StringVector=list)))
    monkeypatch.setattr(harness, 'load_class', lambda _: FakeDut)
    if configured is None:
        monkeypatch.delenv('UCV_SEED', raising=False)
    else:
        monkeypatch.setenv('UCV_SEED', configured)
    loaded = harness.DutHarness('pred_checker', seed=override)
    assert loaded.dut.arguments == ['pred_checker', f'+verilator+seed+{expected}',
                                    '+verilator+rand+reset+0']
    assert loaded.dut.options == {'coverage_filename': ''}
    loaded.finish()
    assert loaded.dut.finished


class _Agent:
    def __init__(self, *, unresolved=False, cleanup_error=False):
        self.unresolved, self.cleanup_error = unresolved, cleanup_error
        self.finished = self.cleaned = 0

    @asynccontextmanager
    async def running(self):
        try:
            yield self
            self.finished += 1
            if self.unresolved:
                raise RuntimeError('unreconciled evaluation')
        finally:
            self.cleaned += 1
            if self.cleanup_error:
                raise ValueError('independent cleanup failure')


def _request(outcome, phase='call'):
    return SimpleNamespace(config=SimpleNamespace(_ifu_phases={
        'test': {phase: {'outcome': outcome}}} if outcome is not None else {}),
        node=SimpleNamespace(nodeid='test'))


@pytest.mark.parametrize('outcome', ['failed', 'skipped'])
@pytest.mark.parametrize('phase', ['setup', 'call'])
def test_reported_nonpass_does_not_become_a_spurious_teardown_error(outcome, phase):
    async def run():
        agent = _Agent(unresolved=True)
        async with harness_fixtures.agent_runtime(_request(outcome, phase), agent):
            pass
        assert agent.finished == 0 and agent.cleaned == 1
    asyncio.run(run())


@pytest.mark.parametrize('outcome', ['passed', None])
def test_swallowed_failure_or_missing_report_still_requires_strict_finish(outcome):
    async def run():
        agent = _Agent(unresolved=True)
        with pytest.raises(RuntimeError, match='unreconciled evaluation'):
            async with harness_fixtures.agent_runtime(_request(outcome), agent):
                pass
        assert agent.finished == 1 and agent.cleaned == 1
    asyncio.run(run())


def test_passing_body_finishes_and_cleans_once():
    async def run():
        agent = _Agent()
        async with harness_fixtures.agent_runtime(_request('passed'), agent):
            pass
        assert agent.finished == agent.cleaned == 1
    asyncio.run(run())


def test_direct_body_exception_preserves_its_identity_and_cleanup():
    async def run():
        agent = _Agent(unresolved=True)
        error = ValueError('original body failure')
        with pytest.raises(ValueError) as caught:
            async with harness_fixtures.agent_runtime(_request(None), agent):
                raise error
        assert caught.value is error and agent.finished == 0 and agent.cleaned == 1
    asyncio.run(run())


def test_reported_nonpass_does_not_suppress_independent_cleanup_errors():
    async def run():
        agent = _Agent(unresolved=True, cleanup_error=True)
        with pytest.raises(ValueError, match='independent cleanup failure'):
            async with harness_fixtures.agent_runtime(_request('failed'), agent):
                pass
        assert agent.cleaned == 1
    asyncio.run(run())
