from suites.frontend.bpu.models.configuration import MAIN_WAYS, MAIN_BANKS, ALIGN_HALFWORDS
"""Normal-driver cleanup/training overlap, checked through passive monitors."""
from copy import deepcopy
from dataclasses import replace

from toffee import CheckContext
from toffee import ScoreboardMode
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.types import MbtbBranchFeedback
from suites.frontend.bpu.mbtb.model.cleanup import expected_mbtb_cleanup_states
from suites.frontend.bpu.mbtb.model.cleanup import expected_mbtb_cleanup_dual
from suites.frontend.bpu.mbtb.model.cleanup import mbtb_entry_slot
from suites.frontend.bpu.mbtb.model.cleanup import observed_mbtb_cleanup_dual
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.mbtb.driver.feedback import observed_mbtb_feedback
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.resident_scenario import READ_WINDOW
from suites.frontend.bpu.mbtb.case.resident_scenario import frozen_check
from suites.frontend.bpu.mbtb.case.resident_scenario import snapshot


KEYS = {'zero_tag': (0, 5), 'zero_position': (1, 0), 'nonzero': (1, 5)}


def feedback(vector, metadata):
    return MbtbBatchTraining(vector.pc, deepcopy(metadata), (
        MbtbBranchFeedback(vector.target, 1, vector.position, vector.branch_type, mispredict=1),))


async def check_case(agent, coverage, align, bank, depth, shadow_state, key, *, key_fields=None):
    await agent.reset()
    tag, position = KEYS[key] if key_fields is None else key_fields
    if (type(tag) is not int or not 0 <= tag < 65536 or
            type(position) is not int or not 0 <= position < 7):
        raise ValueError('cleanup program requires a tag and a position with one later neighbor')
    # DefaultConfig address fields: align=PC[4], internal bank=PC[6:5],
    # set=PC[14:7], tag=PC[30:15].  A fetch start is 32-byte aligned, and the
    # CFI position's bit4 selects the opposite align bank, so both alignment
    # replicas keep a zero start-PC align bit and use position 16+p.
    original = BranchVector(0x40000000 + (tag << 15) + (bank << 5),
                            0x40002340, position + 16 * align, 3)
    # One set stride in the same internal bank, used to recycle the target
    # set's write-buffer shadow before the cold correction allocates it again.
    displacer = replace(original, pc=original.pc + 0x80, target=original.target + 0x1020)
    changed = replace(original, target=original.target + 0x400)
    extra = replace(displacer, position=original.position + 1, target=displacer.target + 0x200)
    updated = replace(extra, target=extra.target + 0x800)
    cold = await agent.predict(original.pc)
    other_cold = await agent.predict(displacer.pc)
    second_cold = await agent.predict(original.pc)
    immutable_originals=deepcopy((cold.meta_entries,other_cold.meta_entries,second_cold.meta_entries))
    for prediction in (cold, other_cold, second_cold):
        assert_miss(prediction)
    dimensions = dict(align=align, bank=bank, depth=depth, shadow_state=shadow_state, key=key)
    sequence = (align, bank, depth, shadow_state, key)
    async with agent.observe_entry_shadow() as shadows, agent.observe_entry_activity() as trace:
        async with agent.defer_multi_hit_cleanup():
            await agent.train_burst((feedback(original, cold.meta_entries),))
            await agent.train_burst((feedback(displacer, other_cold.meta_entries),))
            if depth == 0:
                current = await agent.predict(displacer.pc)
                await agent.train_burst((feedback(extra, current.meta_entries),))
            first = await agent.predict(original.pc)
            assert_vector_hit(first, original)
            base = align * (MAIN_WAYS + 1)
            original_way = matching_way(first, original)
            assert base <= original_way < base + MAIN_WAYS
            other_before = await agent.predict(displacer.pc)
            assert_vector_hit(other_before, displacer)
            if depth == 1:
                sentinel_pc = original.pc + 0x1000
                sentinel = snapshot(await agent.predict(sentinel_pc))
                lookups = [agent.submit_predict(sentinel_pc, expected=frozen_check(sentinel))
                           for _ in range(READ_WINDOW)]
                await agent.train_burst((feedback(changed, second_cold.meta_entries),
                                        feedback(extra, other_before.meta_entries)))
                await agent.drain_predictions()
                for transfer in lookups:
                    await transfer
                other_before = await agent.predict(displacer.pc)
                # Retained ownership is indexed by the physical way the public
                # prediction actually reports, not by a fixed old-geometry slot.
                retained_owner = matching_way(other_before, extra) - align * (MAIN_WAYS + 1)
                agent.entry_scoreboard.check(expected=mbtb_entry_slot(extra),
                    actual=shadows[-1].value['banks'][align][(original.pc >> 5) & (MAIN_BANKS - 1)][retained_owner][1],
                    context=CheckContext(scoreboard='mbtb.cleanup_depth', mode=ScoreboardMode.DIRECT,
                        sequence_id=sequence, request=extra, accepted_event=trace.feedback[-1].event,
                        observed_event=shadows[-1].event))
            else:
                await agent.train_burst((feedback(changed, second_cold.meta_entries),))
            assert_vector_hit(other_before, extra)
            extra_way = matching_way(other_before, extra)
            assert base <= extra_way < base + MAIN_WAYS and extra_way != original_way
            duplicate = await agent.predict(original.pc)
            active = [(index, entry.target) for index, entry in enumerate(duplicate.entries)
                      if base <= index < base + MAIN_WAYS and entry.valid]
            assert sorted(target for _, target in active) == sorted([changed.target, original.target])
            duplicate_ways = [index - base for index, _ in active]
            keep_way, clear_way = min(duplicate_ways), max(duplicate_ways)
            neighbor_way = matching_way(other_before, extra) - base
            wanted = expected_mbtb_cleanup_states(snapshot(duplicate), snapshot(other_before),
                original.pc, align, keep_way, clear_way, neighbor_way, updated.target)
            wanted_dual = expected_mbtb_cleanup_dual(original, changed, extra, updated, depth, shadow_state)
            transaction = feedback(updated, other_before.meta_entries)
            wanted_feedback = expected_mbtb_feedback(transaction,
                branch_count=len(agent.ports.training.bits.branches))
            coverage.sample(dict(dimensions, phase='prepared'))
            first_feedback, first_frame = len(trace.feedback), len(trace.frames)
            await agent.train_during_multi_hit_cleanup(transaction, shadow_state=shadow_state)
        # Replacing cached S2 state stops repeated clears and lets training drain.
        cleaned = await agent.predict(original.pc)
        await agent.retire_multi_hit_cleanup()
        other_after = await agent.predict(displacer.pc)
        accepted = trace.feedback[first_feedback:]
        duals = observed_mbtb_cleanup_dual(trace.frames[first_frame:], shadows, align, bank)
        context = dict(mode=ScoreboardMode.DIRECT, sequence_id=sequence, request=transaction,
            accepted_event=accepted[0].event if accepted else None,
            observed_event=trace.frames[-1].event)
        agent.feedback_scoreboard.check(expected={'beats': 1, 'frames': (wanted_feedback,)},
            actual={'beats': len(accepted), 'frames': tuple(observed_mbtb_feedback(frame.value) for frame in accepted)},
            context=CheckContext(scoreboard='mbtb.cleanup_feedback', **context))
        agent.entry_scoreboard.check(expected={'beats': 1, 'offsets': (4,), 'values': (wanted_dual,)},
            actual={'beats': len(duals), 'offsets': tuple(value['tick'] - accepted[0].event.tick for value in duals),
                    'values': tuple(value['value'] for value in duals)},
            context=CheckContext(scoreboard='mbtb.cleanup_dual', **context))
        agent.entry_scoreboard.check(expected={'cleaned': wanted[0], 'neighbor': wanted[1]},
            actual={'cleaned': snapshot(cleaned), 'neighbor': snapshot(other_after)},
            context=CheckContext(scoreboard='mbtb.cleanup_result', **context))
        coverage.sample(dict(dimensions, phase='overlapped'))
        for order in ((0, 1), (1, 0)):
            pcs = (original.pc, displacer.pc)
            transfers = [agent.submit_predict(pcs[index], expected=frozen_check(wanted[index])) for index in order]
            await agent.drain_predictions()
            for transfer in transfers:
                await transfer
                assert transfer.completed_event.tick - transfer.accepted_event.tick == 4
            assert transfers[1].accepted_event.tick - transfers[0].accepted_event.tick == 2
        coverage.sample(dict(dimensions, phase='revisited'))
        agent.reference.raise_failure()
        assert immutable_originals==(cold.meta_entries,other_cold.meta_entries,second_cold.meta_entries),'original feedback metadata changed'
        status=agent.reference.board.status
        return dict(dimensions, expected_dual=wanted_dual, actual_dual=duals[0]['value'],
            expected_feedback=wanted_feedback, actual_feedback=observed_mbtb_feedback(accepted[0].value),
            request_offset=duals[0]['tick'] - accepted[0].event.tick,
            public_profiles_checked=True, integrated_ftq_reachability_proven=False,
            original_metadata_unchanged=True,independent_reference_checks=status.checked,
            independent_reference_failures=status.failed)
