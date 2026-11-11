"""Real-DUT controls for the production coherent observer; no functional credit."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect

pytestmark = pytest.mark.selftest
PC = 0x40000800


async def test_live_prediction_scope_cannot_close_by_discarding_monitors(bpu_agent):
    checker = BpuPhrChecker(scope='finish-live-input')
    with pytest.raises(RuntimeError, match='stopped prediction acceptance'):
        async with bpu_agent.observe_phr(checker):
            await bpu_agent.reset(PC)
            await bpu_agent.next_transaction(start_pc=PC)


async def test_stopped_monitor_cannot_claim_a_new_recovery_was_accepted(bpu_agent):
    checker = BpuPhrChecker(scope='stopped-monitor')
    with pytest.raises(AssertionError):
        async with bpu_agent.observe_phr(checker) as observation:
            await bpu_agent.reset(PC)
            source = await bpu_agent.next_transaction(start_pc=PC)
            await bpu_agent.set_ready(prediction=False, meta=True)
            await observation.drain()
            await observation.monitor.aclose()
            with pytest.raises(AssertionError):
                await bpu_agent.redirect(BpuRedirect(PC + 0x200, source.meta.redirect))
            # Swallowing the first missed-acceptance error cannot clear the
            # still-planned input when the scope attempts a normal finish.
            assert checker.planned


async def test_swallowed_physical_comparison_still_prevents_clean_finish(bpu_agent, monkeypatch):
    checker = BpuPhrChecker(scope='swallowed-physical-corruption')
    with pytest.raises(AssertionError) as finished:
        async with bpu_agent.observe_phr(checker) as observation:
            await bpu_agent.reset(PC)
            await bpu_agent.next_transaction(start_pc=PC)
            observe = checker.observe

            def corrupt(sample):
                actual = deepcopy(sample.value)
                cells = list(actual['state']['cells'])
                cells[-1] ^= 1
                actual['state']['cells'] = tuple(cells)
                observe(SimpleNamespace(value=actual, event=sample.event))

            monkeypatch.setattr(checker, 'observe', corrupt)
            with pytest.raises(AssertionError) as first:
                await observation.settle(1)
            monkeypatch.setattr(checker, 'observe', observe)
            assert first.value is checker.failure
    assert finished.value is checker.failure


async def test_reset_records_cancelled_uids_and_new_epoch_without_a_pointer_flag(bpu_agent):
    checker = BpuPhrChecker(scope='reset-identity')
    async with bpu_agent.observe_phr(checker) as observation:
        await bpu_agent.reset(PC)
        original = await bpu_agent.next_transaction(start_pc=PC)
        live = set(checker.association.pending)
        assert live
        await bpu_agent.reset(PC)
        current = await bpu_agent.next_transaction(start_pc=PC)
        assert current.uid > original.uid and current.epoch > original.epoch
        cancelled = {row['uid'] for row in checker.association.cancellations if row['reason'] == 'reset'}
        completed = {uid for uid, _, _ in checker.association.completions}
        # Reset itself is a driven transaction with a launch boundary. Older
        # leases may complete before that edge; those must not be relabelled
        # as cancelled. Check both terminal paths by UID, not a guessed delay.
        assert cancelled and live <= completed | cancelled
        assert not completed & cancelled
        assert set(current.meta.redirect['phr']['phrPtr']) == {'value'}
        await bpu_agent.set_ready(prediction=False, meta=True)
        await observation.drain()
    assert checker.summary()['outstanding'] == 0
