"""Real encoder faults must not redefine the independently frozen input plan."""
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.testbenches.mbtb.tests.framework.test_mbtb_runtime_obligations import running, training

pytestmark = [pytest.mark.selftest, pytest.mark.dut('mbtb')]


@pytest.mark.parametrize('field', ('rawHit', 'position'))
async def test_corrupted_victim_identity_is_rejected_on_the_actual_training_wire(dut_factory, monkeypatch, field):
    await check_corrupted_identity(dut_factory, monkeypatch, field, alignment=0)


@pytest.mark.parametrize('field', ('rawHit', 'position'))
async def test_second_alignment_victim_corruption_is_rejected_on_the_actual_wire(dut_factory, monkeypatch, field):
    await check_corrupted_identity(dut_factory, monkeypatch, field, alignment=1)


async def check_corrupted_identity(dut_factory, monkeypatch, field, *, alignment):
    async with running(dut_factory) as agent:
        await agent.reset()
        source = await agent.predict(0x80000000)
        encoder = agent._encode_training
        injected = []
        def wrong(tx):
            payload = encoder(tx)
            payload['meta_entries'][alignment][4][field] ^= 1
            injected.append(field)
            return payload
        monkeypatch.setattr(agent, '_encode_training', wrong)
        with pytest.raises(ScoreboardMismatch) as caught:
            await agent.train_batch(training(source))
        assert caught.value.name == 'mbtb.planned-training-input' and injected == [field]
        with pytest.raises(ScoreboardMismatch) as later:
            await agent.finish()
        assert later.value is caught.value
