from types import SimpleNamespace

import pytest

from bpuverify.tage.agent.main import TageAgent


async def test_shadow_scope_requires_started_agent():
    with pytest.raises(RuntimeError, match='requires a started'):
        async with TageAgent.observe_shadows(SimpleNamespace(_execution=None)):
            pytest.fail('unstarted shadow scope entered')


async def test_shadow_scope_rejects_nested_observation():
    agent = SimpleNamespace(_execution=object(), _shadow_observation_active=True)
    with pytest.raises(RuntimeError, match='already active'):
        async with TageAgent.observe_shadows(agent):
            pytest.fail('nested shadow scope entered')


@pytest.mark.parametrize('where', ('start', 'body', 'close', 'none'))
async def test_shadow_scope_cleans_active_flag_after_each_exit(where):
    calls = []
    def start(execution, *, observer):
        calls.append('start')
        if where == 'start':
            raise RuntimeError('injected start failure')
        observer('captured')
    async def close():
        calls.append('close')
        if where == 'close':
            raise RuntimeError('injected close failure')
    agent = SimpleNamespace(_execution=object(), _shadow_observation_active=False,
        _shadow_monitor=SimpleNamespace(start=start, aclose=close))
    async def operation():
        async with TageAgent.observe_shadows(agent) as observations:
            assert agent._shadow_observation_active and observations == ['captured']
            if where == 'body':
                raise RuntimeError('injected body failure')
    if where == 'none':
        await operation()
    else:
        with pytest.raises(RuntimeError, match=f'injected {where} failure'):
            await operation()
    assert calls == ['start', 'close']
    assert not agent._shadow_observation_active
