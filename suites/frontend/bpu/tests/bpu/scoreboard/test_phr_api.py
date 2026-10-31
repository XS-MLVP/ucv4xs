"""Public recovery encoding and coherent-observation ownership contracts."""

from types import SimpleNamespace

import pytest

from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.phr.observation import BpuPhrObservation
from suites.frontend.bpu.bpu.checker.phr.association import BpuPhrAssociation


def test_legacy_redirect_and_metadata_are_preserved_without_aliasing():
    meta = {'phr': {'phrPtr': {'flag': 1, 'value': 50}, 'phrLowBits': 3}}
    payload = BpuRedirect(0x40000800, meta).payload()
    assert payload == dict(target=0x40000800, cfi_pc=0x40000800,
                          taken=1, branch_type=2, ras_action=0, meta=meta)
    payload['meta']['phr']['phrLowBits'] = 99
    assert meta['phr']['phrLowBits'] == 3


def test_explicit_not_taken_recovery_has_distinct_branch_and_target():
    payload = BpuRedirect(0x40000810, {}, cfi_pc=0x4000080F,
                          taken=0, branch_type=1).payload()
    assert payload == dict(target=0x40000810, cfi_pc=0x4000080F,
                          taken=0, branch_type=1, ras_action=0, meta={})


@pytest.mark.parametrize('action',range(4))
def test_redirect_exposes_ras_action_without_changing_checkpoint_or_branch(action):
    metadata = dict(ras=dict(ssp=1,sctr=6,tosw=dict(flag=0,value=7)))
    payload = BpuRedirect(0x40018010,metadata,cfi_pc=0x4001800f,ras_action=action).payload()
    assert payload['ras_action']==action and payload['meta']==metadata
    assert (payload['target'],payload['cfi_pc'],payload['taken'],payload['branch_type'])==(0x40018010,0x4001800f,1,2)


async def test_default_redirect_clears_previous_redo_action_in_driver_payload():
    agent = fake_agent()
    payloads = []
    async def send(payload):
        payloads.append(payload)
        return SimpleNamespace(tick=len(payloads)*2)
    agent.redirect_driver = SimpleNamespace(send=send)
    assert await agent.redirect(BpuRedirect(0x40018000,{},ras_action=2))==2
    assert await agent.redirect(BpuRedirect(0x40018010,{}))==4
    assert [payload['ras_action'] for payload in payloads]==[2,0]


def test_legacy_sign_guard_pc_keeps_port_truncation():
    payload = BpuRedirect((1 << 49) + 12, {}).payload()
    assert payload['target'] == (1 << 49) + 12
    assert payload['cfi_pc'] == 12


@pytest.mark.parametrize('field,width', (('pc', 50), ('cfi_pc', 49),
                                        ('taken', 1), ('branch_type', 2), ('ras_action', 2)))
@pytest.mark.parametrize('bad', ('negative', 'overflow', 'bool', 'float'))
def test_redirect_fields_reject_invalid_values_before_driving(field, width, bad):
    value = {'negative': -1, 'overflow': 1 << width, 'bool': True, 'float': 1.0}[bad]
    arguments = dict(pc=0, meta={})
    arguments[field] = value
    with pytest.raises(ValueError, match=field):
        BpuRedirect(**arguments).payload()


class StreamMonitor:
    def __init__(self):
        self.closed = False
        self.started = None

    async def aclose(self):
        self.closed = True

    def start(self, execution):
        self.started = execution


class CoherentMonitor(StreamMonitor):
    def __init__(self, agent):
        super().__init__()

    def start(self, execution, *, observer):
        self.started = execution
        self.observer = observer


def fake_agent():
    agent = object.__new__(BpuAgent)
    agent._started = True
    agent._execution = object()
    agent._phr_observation = None
    agent._transaction_aligned = True
    agent.prediction_monitor = StreamMonitor()
    agent.meta_monitor = StreamMonitor()
    def renew():
        agent.prediction_monitor = StreamMonitor()
        agent.meta_monitor = StreamMonitor()
    agent._make_stream_monitors = renew
    return agent


async def test_prediction_drain_requires_stopped_younger_reads():
    agent = fake_agent()
    agent._prediction_ready = 1
    with pytest.raises(RuntimeError, match='backpressure'):
        await agent.drain_prediction_work()


async def test_prediction_drain_uses_actual_activity_contract():
    agent, calls, result = fake_agent(), [], object()
    agent._prediction_ready = 0
    async def wait_idle(*groups):
        calls.append(groups)
        return result
    agent.training_activity = SimpleNamespace(wait_idle=wait_idle)
    assert await agent.drain_prediction_work() is result
    assert calls == [('reads', 'pipeline', 'writes', 'fast_pipeline', 'fast_writes')]


async def test_observation_drain_checks_latched_failures_before_and_after():
    checks, result = [], object()
    agent = fake_agent()
    async def drain():
        checks.append('drain')
        return result
    agent.drain_prediction_work = drain
    checker = SimpleNamespace(raise_failure=lambda: checks.append('check'))
    observation = BpuPhrObservation(agent, checker)
    agent._phr_observation, observation._active = observation, True
    assert await observation.drain() is result
    assert checks == ['check', 'drain', 'check']


@pytest.fixture
def coherent_monitor(monkeypatch):
    monkeypatch.setattr('suites.frontend.bpu.bpu.env.phr.observation.BpuPhrMonitor', CoherentMonitor)


async def test_ownership_closes_old_streams_and_starts_fresh_streams(coherent_monitor):
    agent = fake_agent()
    previous = agent.prediction_monitor, agent.meta_monitor
    checker = BpuPhrChecker(scope='ownership')
    async with agent.observe_phr(checker) as observation:
        assert agent._phr_observation is observation
        assert all(monitor.closed for monitor in previous)
        assert observation.monitor.observer == checker.capture
        with pytest.raises(RuntimeError, match='owns the streams'):
            await agent.next_meta()
        with pytest.raises(RuntimeError, match='already owns'):
            async with agent.observe_phr(checker):
                pytest.fail('nested coherent scopes are not allowed')
    assert agent._phr_observation is None
    assert observation.monitor.closed
    assert agent.prediction_monitor is not previous[0]
    assert agent.meta_monitor is not previous[1]
    assert agent.prediction_monitor.started is agent._execution
    assert agent.meta_monitor.started is agent._execution
    assert not agent._transaction_aligned
    with pytest.raises(RuntimeError, match='not active'):
        await observation.next_transaction()


async def test_body_failure_is_preserved_and_streams_recover(coherent_monitor):
    agent = fake_agent()
    checker = BpuPhrChecker(scope='failure')
    error = AssertionError('original foreground mismatch')
    with pytest.raises(AssertionError) as caught:
        async with agent.observe_phr(checker):
            checker.failure = error
            raise error
    assert caught.value is error
    assert agent._phr_observation is None
    assert agent.prediction_monitor.started is agent._execution


async def test_latent_checker_failure_is_raised_on_clean_scope_exit(coherent_monitor):
    agent = fake_agent()
    checker = BpuPhrChecker(scope='late failure')
    error = AssertionError('last observed mismatch')
    with pytest.raises(AssertionError) as caught:
        async with agent.observe_phr(checker):
            checker.failure = error
    assert caught.value is error
    assert agent._phr_observation is None


async def test_binding_failure_does_not_close_existing_streams(monkeypatch):
    agent = fake_agent()
    original = agent.prediction_monitor, agent.meta_monitor
    def unavailable(agent):
        raise RuntimeError('memory-direct leaf unavailable')
    monkeypatch.setattr('suites.frontend.bpu.bpu.env.phr.observation.BpuPhrMonitor', unavailable)
    with pytest.raises(RuntimeError, match='memory-direct leaf unavailable'):
        async with agent.observe_phr(BpuPhrChecker(scope='binding')):
            pytest.fail('binding should fail before ownership changes')
    assert agent._phr_observation is None
    assert not any(monitor.closed for monitor in original)


async def test_subscription_start_failure_restores_streams(monkeypatch):
    agent = fake_agent()
    class CannotStart(CoherentMonitor):
        def start(self, *args, **kwargs):
            raise RuntimeError('subscription failed')
    monkeypatch.setattr('suites.frontend.bpu.bpu.env.phr.observation.BpuPhrMonitor', CannotStart)
    with pytest.raises(RuntimeError, match='subscription failed'):
        async with agent.observe_phr(BpuPhrChecker(scope='subscription')):
            pytest.fail('subscription cannot start')
    assert agent._phr_observation is None
    assert agent.prediction_monitor.started is agent._execution


async def test_shutdown_does_not_restart_streams(coherent_monitor):
    agent = fake_agent()
    async with agent.observe_phr(BpuPhrChecker(scope='shutdown')) as observation:
        await observation.aclose(resume_streams=False)
        await observation.aclose()
        assert agent.prediction_monitor.closed
        assert agent.meta_monitor.closed
    assert agent._phr_observation is None


async def test_unstarted_agent_refuses_observation():
    agent = fake_agent()
    agent._started = False
    with pytest.raises(RuntimeError, match='active Execution'):
        async with agent.observe_phr(BpuPhrChecker(scope='unstarted')):
            pytest.fail('agent is not running')


@pytest.mark.parametrize('bad', (0, -1, True, 1.5))
async def test_causal_association_rejects_invalid_limit(bad):
    with pytest.raises(ValueError, match='positive integer'):
        await BpuPhrAssociation().next_transaction(None, None, limit=bad)


@pytest.mark.parametrize('require_taken', (False, True))
async def test_causal_selection_has_strict_acceptance_boundary(require_taken):
    association = BpuPhrAssociation()
    items = [SimpleNamespace(prediction_tick=tick,
              prediction=SimpleNamespace(start_pc=0x100, taken=taken))
             for tick, taken in ((20, 1), (22, 0), (24, 1))]
    association.completed.extend(items)
    checker = BpuPhrChecker(scope='selection')
    result = await association.next_transaction(None, checker, start_pc=0x100,
        after_tick=20, require_taken=require_taken)
    assert result is items[2 if require_taken else 1]
