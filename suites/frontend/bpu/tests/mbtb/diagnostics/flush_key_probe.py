"""Standalone diagnostic, deliberately excluded from automatic test collection.

Run run_flush_key_probe.py to isolate reports. A failure here is not an
integrated FTQ reachability proof and is not registered as strict XFAIL.
"""
from copy import deepcopy
from dataclasses import asdict
from dataclasses import replace

import pytest
from toffee import CheckContext
from toffee import ClockCycles
from toffee import ScoreboardMode
from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.mbtb.transaction.types import MbtbBatchTraining
from bpuverify.mbtb.transaction.types import MbtbBranchFeedback
from bpuverify.mbtb.transaction.types import MbtbTraining
from tests.conftest import dut_factory
from bpuverify.common.env.fixtures import agent_fixture
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import matching_way
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.resident_scenario import frozen_check
from bpuverify.mbtb.case.resident_scenario import snapshot

CASES = []

class CleanupOverlapAgent(MbtbAgent):
    async def retire_cleanup_writebacks(self):
        """Retire queued writes after a fresh lookup replaces cached multi-hit."""
        await ClockCycles(self.dut.clock, 6)

    async def resume_cleanup_and_train(self, transaction, delay_cycles=0):
        if not self._defer_multi_hit_cleanup:
            raise RuntimeError('requires deferred cleanup scope')
        self._defer_multi_hit_cleanup = False
        self.lookup_driver.quiesce()
        if delay_cycles:
            await ClockCycles(self.dut.clock, delay_cycles)
        await self.train_burst((transaction,))

mbtb_agent = agent_fixture('mbtb', CleanupOverlapAgent, max_batch_ticks=128)

def state(prediction):
    return dict(entries=[asdict(entry) for entry in prediction.entries],
                meta_entries=deepcopy(prediction.meta_entries))

def activity(trace):
    values = []
    for frame in trace.frames:
        for align, row in enumerate(frame.value['banks']):
            for bank, ports in enumerate(row):
                for way, port in enumerate(ports):
                    if port['write_valid'] or port['read_valid']:
                        values.append(dict(tick=frame.event.tick, align=align, bank=bank, way=way, **port))
    return values

@pytest.mark.parametrize('tag', (0, 1))
@pytest.mark.parametrize('position', (0, 5))
@pytest.mark.parametrize('overlap', (False, True))
@pytest.mark.parametrize('train_way', (0, 1))
@pytest.mark.parametrize('depth', (0, 1))
@pytest.mark.parametrize('delay', (0, 1))
@pytest.mark.parametrize('align', (0, 1))
@pytest.mark.parametrize('bank', (0, 1))
async def test_flush_key(mbtb_agent, tag, position, overlap, train_way, depth, delay, align, bank):
    agent = mbtb_agent
    await agent.reset()
    original = BranchVector(0x40000020 + (tag << 11) + (bank << 4), 0x40002340, position + 8 * align, 3)
    displacer = replace(original, pc=original.pc + 64, target=original.target + 0x1020)
    cold = await agent.predict(original.pc)
    assert_miss(cold)
    other_cold = await agent.predict(displacer.pc)
    assert_miss(other_cold)
    second_cold = await agent.predict(original.pc)
    assert_miss(second_cold)

    def feedback(vector, metadata):
        return MbtbBatchTraining(vector.pc, deepcopy(metadata), (
            MbtbBranchFeedback(vector.target, 1, vector.position, vector.branch_type, mispredict=1),))

    changed = replace(original, target=original.target + 0x400)
    case = dict(tag=tag, position=position, overlap=overlap, train_way=train_way,
                depth=depth, delay=delay, align=align, bank=bank,
                integrated_ftq_reachability_proven=False)
    CASES.append(case)
    async with agent.observe_entry_shadow() as shadows, agent.observe_entry_activity() as trace:
        async with agent.defer_multi_hit_cleanup():
            await agent.train_burst((feedback(original, cold.meta_entries),))
            await agent.train_burst((feedback(displacer, other_cold.meta_entries),))
            training_resident = displacer
            extra = replace(displacer, position=original.position + 1, target=displacer.target + 0x200)
            if train_way == 0 and depth == 0:
                training_resident = extra
                other_first = await agent.predict(displacer.pc)
                await agent.train_burst((feedback(training_resident, other_first.meta_entries),))
            first = await agent.predict(original.pc)
            assert_vector_hit(first, original)
            assert matching_way(first, original) == align * 2 + 1
            case['first'] = state(first)
            other_before = await agent.predict(displacer.pc)
            assert_vector_hit(other_before, displacer)
            assert_vector_hit(other_before, training_resident)
            if depth == 1:
                sentinel_pc = original.pc + 128
                sentinel = snapshot(await agent.predict(sentinel_pc))
                lookups = [agent.submit_predict(sentinel_pc, expected=frozen_check(sentinel)) for _ in range(24)]
                await agent.train_burst((feedback(changed, second_cold.meta_entries),
                                        feedback(extra, other_before.meta_entries)))
                await agent.drain_predictions()
                for transfer in lookups:
                    await transfer
                other_before = await agent.predict(displacer.pc)
                assert_vector_hit(other_before, extra)
                assert matching_way(other_before, extra) == align * 2
                if train_way == 0:
                    training_resident = extra
                slot = shadows[-1].value['banks'][align][bank][0][1]
                expected_slot = dict(valid=1, dirty=0, set_idx=(extra.pc >> 5) & 63,
                    tag=(extra.pc >> 11) & 65535, branch_type=3, ras_action=0,
                    position=extra.position % 8, carry=0, lower=extra.target % (1 << 20))
                case['depth_one'] = dict(expected=expected_slot, actual=slot)
                agent.entry_scoreboard.check(expected=expected_slot, actual=slot,
                    context=CheckContext(scoreboard='mbtb.cleanup_depth', mode=ScoreboardMode.DIRECT,
                        sequence_id=len(CASES), request=extra, accepted_event=trace.feedback[-1].event,
                        observed_event=shadows[-1].event))
            else:
                await agent.train_burst((feedback(changed, second_cold.meta_entries),))
            assert matching_way(other_before, training_resident) == align * 2 + train_way
            double = await agent.predict(original.pc)
            case['double'] = state(double)
            assert [(way, entry.target) for way, entry in enumerate(double.entries) if entry.valid] == [
                (align * 2, changed.target), (align * 2 + 1, original.target)]
            expected_clean = state(double)
            expected_clean['entries'][align * 2 + 1].update(valid=0, target=original.pc & ~((1 << 20) - 1),
                                                position=align * 8, branch_type=0, ras_action=0)
            expected_clean['meta_entries'][align][1].update(
                rawHit=0, position=align * 8, attribute=dict(branchType=0, rasAction=0))
            expected_other = state(other_before)
            if overlap:
                expected_other['entries'][align * 2 + train_way]['target'] += 0x800
            case['expected_clean'] = expected_clean
            case['expected_other'] = expected_other
            if overlap:
                # Rewrite the different-set resident while the duplicate flush
                # advances independently on the lookup path.
                updated = replace(training_resident, target=training_resident.target + 0x800)
                case['release_tick'] = trace.frames[-1].event.tick
                await agent.resume_cleanup_and_train(feedback(updated, other_before.meta_entries), delay)
            else:
                updated = training_resident
        case['activity'] = activity(trace)
        case['feedback_ticks'] = [frame.event.tick for frame in trace.feedback]
        cleaned = await agent.predict(original.pc)
        case['shadow_before_retire'] = deepcopy(shadows[-1].value['banks'][align][bank])
        await agent.retire_cleanup_writebacks()
        other_after = await agent.predict(displacer.pc)
        case['cleaned'] = state(cleaned)
        case['other_after'] = state(other_after)
        case['shadow_after_retire'] = deepcopy(shadows[-1].value['banks'][align][bank])
        context = CheckContext(scoreboard='mbtb.flush_key', mode=ScoreboardMode.DIRECT,
                               sequence_id=len(CASES), request=dict(tag=tag, position=position,
                               overlap=overlap, train_way=train_way, feedback=updated),
                               accepted_event=trace.feedback[-1].event,
                               observed_event=trace.frames[-1].event)
        agent.entry_scoreboard.check(expected=dict(cleaned=expected_clean, other=expected_other),
            actual=dict(cleaned=case['cleaned'], other=case['other_after']), context=context)
