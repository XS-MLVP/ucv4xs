import asyncio
from types import SimpleNamespace

import pytest

from bpuverify.tage.agent.main import TageAgent
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.tage.transaction.types import TageLookup


def fake_agent():
    # Any attempted drain/submission is an error in a preflight rejection test.
    return SimpleNamespace(reference=SimpleNamespace(raise_failure=lambda: None),
                           encode_batch_training=lambda transaction: {'encoded': transaction},
                           _main_btb=lambda request: {'validated': request})


async def test_empty_pressure_feedback_rejects_before_drive():
    with pytest.raises(ValueError, match='must not be empty'):
        await TageAgent.train_batches_with_read_pressure(fake_agent(), (), TageLookup(0, 6, 1))


async def test_pressure_requires_domain_lookup_request_before_drive():
    with pytest.raises(TypeError, match='TageLookup'):
        await TageAgent.train_batches_with_read_pressure(fake_agent(), (object(),), object())


@pytest.mark.parametrize('pc,mispredict,use_provider,has_alt,message', (
    (1, 0, 1, 0, 'same-bank'), (0, 1, 1, 0, 'SRAM rereads'), (0, 0, 0, 1, 'SRAM rereads')))
async def test_pressure_rejects_foreign_bank_or_read_conflict_before_submission(pc, mispredict, use_provider, has_alt, message):
    feedback = TageBatchTraining(pc, (TageBranchFeedback(6, 1, 1,
        {'useProvider':use_provider, 'hasAlt':has_alt}, mispredict=mispredict),))
    with pytest.raises(ValueError, match=message):
        await TageAgent.train_batches_with_read_pressure(fake_agent(), (feedback,), TageLookup(0, 6, 1))


async def test_bad_later_feedback_is_encoded_before_any_submission():
    agent = fake_agent()
    def encode(transaction):
        if transaction is None:
            raise ValueError('later beat is invalid')
        return {}
    agent.encode_batch_training = encode
    feedback = TageBatchTraining(0, ())
    with pytest.raises(ValueError, match='later beat is invalid'):
        await TageAgent.train_batches_with_read_pressure(agent, (feedback, None), TageLookup(0, 6, 1))


@pytest.mark.parametrize('failure', (None, RuntimeError, asyncio.CancelledError))
async def test_pressure_schedule_or_failure_always_quiesces_owned_drivers(monkeypatch, failure):
    import bpuverify.tage.agent.main as module
    calls = []
    async def cycles(clock, count):
        assert clock == 'clock'
        calls.append(('cycles', count))
        await asyncio.sleep(0)
    async def drain():
        calls.append('drain')
    async def send_many(encoded):
        calls.append(('send', encoded))
        if failure is not None:
            raise failure('injected pressure failure')
    def submit(*args, **kwargs):
        calls.append('submit')
        return SimpleNamespace(cancel=lambda: calls.append('cancel'))
    async def wait_active(*groups):
        calls.append(('active', groups))
        # Let the owned reader task launch before the simulated status arrives.
        await asyncio.sleep(0)
    async def wait_idle(*groups):
        calls.append(('idle', groups))
    agent = fake_agent()
    agent.dut = SimpleNamespace(clock='clock')
    agent.drain_predictions = drain
    agent.submit_predict = submit
    agent.training_driver = SimpleNamespace(send_many=send_many)
    agent.training_activity = SimpleNamespace(wait_active=wait_active, wait_idle=wait_idle)
    agent.lookup_driver = SimpleNamespace(quiesce=lambda: calls.append('lookup_idle'))
    agent.base_driver = SimpleNamespace(quiesce=lambda: calls.append('base_idle'))
    agent._last_s0_lookup = object()
    feedback = TageBatchTraining(0, (TageBranchFeedback(6, 1, 1, {'useProvider':1, 'hasAlt':0}),))
    monkeypatch.setattr(module, 'ClockCycles', cycles)
    operation = TageAgent.train_batches_with_read_pressure(agent, (feedback,), TageLookup(0, 14, 1))
    if failure is None:
        assert len(await operation) >= 1
        assert calls[-4:] == ['drain', 'lookup_idle', 'base_idle', ('idle', ('pipeline', 'writes'))]
    else:
        with pytest.raises(failure, match='injected pressure failure'):
            await operation
        assert calls[-2:] == ['lookup_idle', 'base_idle']
        assert not any(call == ('idle', ('pipeline', 'writes')) for call in calls)
    assert calls[0] == 'drain' and calls.count('submit') >= 1
    assert ('active', ('reads',)) in calls
    assert agent._last_s0_lookup is None
