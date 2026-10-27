"""Real signal ownership/cleanup and canonical payload compatibility."""
import pytest

from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.env.state.session import StateObservation
from bpuverify.abtb.driver.state.training_driver import AcceptedPulseDriver
from bpuverify.abtb.checker.state.writebuffer import CapacityChecker
from bpuverify.abtb.monitor.state.writebuffer import CapacityMonitor
from bpuverify.abtb.case.state.vectors import interior_set_vectors


@pytest.mark.parametrize('bank', (0, 3))
@pytest.mark.parametrize('failure', ('none','body','pending','setup'))
async def test_state_scope_restores_real_training_after_each_exit(abtb_agent, monkeypatch, bank, failure):
    agent = abtb_agent
    original = agent.training_driver
    checker = CapacityChecker(scope=f'handoff-{failure}-bank{bank}')
    monitor = CapacityMonitor(agent)
    driver = AcceptedPulseDriver(agent.ports.training, checker=checker)
    session = StateObservation(agent, monitor, checker, driver=driver)
    vector = interior_set_vectors(bank, 5, count=1)[0]
    handles = []

    def training(prediction):
        return AbtbTraining(pc=vector.pc, target=vector.target, taken=1, position=vector.position,
                            branch_type=1, meta=prediction.meta)

    async def use():
        async with session:
            cold = await agent.predict(vector.pc, path_hash=bank)
            transaction = training(cold)
            if failure == 'pending':
                for _ in range(3):
                    checker.plan(transaction)
                    handles.append(driver.send(agent.encode_training(transaction)))
                raise RuntimeError('intentional-pending-exit')
            checker.plan(transaction)
            # This ordinary agent method must work with the replacement too.
            await agent.train_under_read_pressure(transaction)
            checker.raise_failure()
            if failure == 'body':
                raise RuntimeError('intentional-body-exit')
            await agent.drain_bank_writes()
            checker.summary()

    with monkeypatch.context() as patch:
        if failure == 'setup':
            reset = agent.reset
            async def failing_reset():
                await reset()
                raise RuntimeError('intentional-setup-exit')
            patch.setattr(agent, 'reset', failing_reset)
        if failure == 'none':
            await use()
        else:
            with pytest.raises(RuntimeError, match=f'intentional-{failure}-exit'):
                await use()
    assert agent.training_driver is original
    assert not driver.has_outstanding
    assert all(handle.done() and handle.accepted_event is None for handle in handles)
    assert monitor._subscription is None
    # Prove the restored owner can really drive normal training, not only that
    # a Python attribute was restored. No private IO or explicit edge waits.
    await agent.reset()
    cold = await agent.predict(vector.pc, path_hash=bank)
    await agent.train(training(cold))
    actual = await agent.predict(vector.pc, path_hash=bank)
    entries = [entry for entry in actual.entries if entry.valid]
    assert len(entries) == 1
    entry, = entries
    assert (entry.target,entry.position,entry.branch_type,entry.ras_action,entry.taken) == (
        vector.target,vector.position,1,0,1)
