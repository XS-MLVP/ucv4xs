"""Recovery bubbles are allowed, but every accepted payload is checked."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.case.early_source import check_resumed_arbitration
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction, BpuStage1Source


def agent_for(ticks, fault=None):
    calls = []
    iterator = iter(ticks)
    agent = SimpleNamespace(calls=calls, micro_only=False)
    held_targets = iter((100, 200, 100))

    async def configure_predictors(**enabled):
        calls.append(('configure', enabled))
        agent.micro_only = not enabled['abtb']

    async def redirect(transaction):
        calls.append(('redirect', transaction))
        return 10

    async def set_ready(**ready):
        calls.append(('ready', ready))
        return 10

    async def next_transaction(**request):
        tick = 12 if agent.micro_only else next(iterator)
        calls.append(('readback' if agent.micro_only else 'accepted', tick, request))
        actual = SimpleNamespace(prediction_tick=tick, meta_tick=tick + 4,
            prediction=BpuPrediction(100, next(held_targets) if agent.micro_only else 100, 1, 4, 0, 0),
            meta=SimpleNamespace(perf=SimpleNamespace(s1_source=
                BpuStage1Source.UBTB if agent.micro_only else BpuStage1Source.ABTB),
                resolve={'utage': {'abtbResult': ({'valid': 1, 'cfiPosition': 4},)}}))
        if fault and not agent.micro_only:
            fault(actual)
        return actual

    async def drain_prediction_work():
        calls.append(('drained',))

    async def train_batches_with_prediction_pause(transactions):
        calls.append(('feedback', transactions))
        return (20, 22, 24, 26)

    agent.configure_predictors = configure_predictors
    agent.redirect = redirect
    agent.set_ready = set_ready
    agent.next_transaction = next_transaction
    agent.drain_prediction_work = drain_prediction_work
    agent.train_batches_with_prediction_pause = train_batches_with_prediction_pause
    return agent


async def test_recovery_bubble_then_adjacent_pair_checks_all_accepted_inputs():
    agent = agent_for((12, 16, 18))
    pair = await check_resumed_arbitration(agent, pc=100, target=100, position=4, checkpoint={'real': 1},
        resolve_meta={'real': 2}, micro_target=200)
    assert [actual.prediction_tick for actual in pair] == [16, 18]
    accepted = [call for call in agent.calls if call[0] == 'accepted']
    assert [call[2]['after_tick'] for call in accepted] == [10, 12, 16]
    assert ('ready', {'prediction': False, 'meta': True}) in agent.calls
    assert agent.calls[-2:] == [('ready', {'prediction': False, 'meta': True}), ('drained',)]
    feedback = [call for call in agent.calls if call[0] == 'feedback']
    assert len(feedback) == 2 and all(len(call[1]) == 4 for call in feedback)


@pytest.mark.parametrize('field', ('target', 'taken', 'position', 's2_override', 's3_override',
    'source', 'valid', 'cfiPosition'))
async def test_bad_payload_before_adjacent_pair_is_not_filtered_out(field):
    def fault(actual):
        if field == 'source':
            actual.meta.perf.s1_source = BpuStage1Source.UBTB
        elif field in ('valid', 'cfiPosition'):
            actual.meta.resolve['utage']['abtbResult'][0][field] ^= 1
        else:
            actual.prediction = replace(actual.prediction, **{field: getattr(actual.prediction, field) ^ 1})
    agent = agent_for((12, 16, 18), fault)
    with pytest.raises(ScoreboardMismatch):
        await check_resumed_arbitration(agent, pc=100, target=100, position=4, checkpoint={'real': 1},
            resolve_meta={'real': 2}, micro_target=200)
    assert len([call for call in agent.calls if call[0] == 'accepted']) == 1
    assert agent.calls[-1] == ('ready', {'prediction': False, 'meta': True})


async def test_no_adjacent_acceptance_fails_with_backpressure_restored():
    agent = agent_for(range(12, 12 + 512, 4))
    with pytest.raises(ScoreboardMismatch, match='adjacent_accepted_requests'):
        await check_resumed_arbitration(agent, pc=100, target=100, position=4, checkpoint={'real': 1},
            resolve_meta={'real': 2}, micro_target=200)
    assert agent.calls[-1] == ('ready', {'prediction': False, 'meta': True})


@pytest.mark.parametrize('readback_number', (1, 2, 3))
async def test_each_public_micro_readback_rejects_a_stale_or_corrupt_target(readback_number):
    agent = agent_for((12, 16, 18))
    original = agent.next_transaction
    readbacks = 0

    async def corrupted(**request):
        nonlocal readbacks
        actual = await original(**request)
        if agent.micro_only:
            readbacks += 1
            if readbacks == readback_number:
                actual.prediction = replace(actual.prediction, target=actual.prediction.target ^ 1)
        return actual

    agent.next_transaction = corrupted
    with pytest.raises(ScoreboardMismatch, match='MicroBTB'):
        await check_resumed_arbitration(agent, pc=100, target=100, position=4, checkpoint={'real': 1},
            resolve_meta={'real': 2}, micro_target=200)
    assert readbacks == readback_number
    assert agent.calls[-1] == ('ready', {'prediction': False, 'meta': True})


@pytest.mark.parametrize('accepted_ticks', ((), (20, 22, 26, 28)))
async def test_missing_or_nonadjacent_resolve_acceptance_cannot_earn_pipeline_credit(accepted_ticks):
    agent = agent_for((12, 16, 18))

    async def bad_burst(transactions):
        return accepted_ticks

    agent.train_batches_with_prediction_pause = bad_burst
    with pytest.raises(ScoreboardMismatch, match='resolve_retarget_burst'):
        await check_resumed_arbitration(agent, pc=100, target=100, position=4, checkpoint={'real': 1},
            resolve_meta={'real': 2}, micro_target=200)
    assert not any(call[0] == 'accepted' for call in agent.calls)
