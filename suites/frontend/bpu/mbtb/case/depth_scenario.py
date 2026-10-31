from suites.frontend.bpu.models.configuration import MAIN_WAYS, MAIN_BANKS, ALIGN_HALFWORDS
"""Fill depth one by normal read pressure, then cross its retained owner."""
from copy import deepcopy
from dataclasses import replace

from toffee import CheckContext
from toffee import ScoreboardMode
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining
from suites.frontend.bpu.mbtb.transaction.types import MbtbBranchFeedback
from suites.frontend.bpu.mbtb.model.entry import mbtb_retarget_targets
from suites.frontend.bpu.mbtb.model.entry import summarize_mbtb_entry_activity
from suites.frontend.bpu.mbtb.model.depth import expected_mbtb_depth_one_states
from suites.frontend.bpu.mbtb.model.entry_keys import mbtb_bank_coordinate
from suites.frontend.bpu.mbtb.model.entry_keys import expected_mbtb_entry_keys_activity
from suites.frontend.bpu.mbtb.model.shadow import expected_mbtb_shadow_activity
from suites.frontend.bpu.mbtb.model.shadow import require_mbtb_shadow_cold_metadata
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.assertions import assert_vector_hit
from suites.frontend.bpu.mbtb.checker.assertions import matching_way
from suites.frontend.bpu.mbtb.checker.assertions import matching_counter
from suites.frontend.bpu.mbtb.checker.depth import defined_depth_check
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.resident_scenario import READ_WINDOW
from suites.frontend.bpu.mbtb.case.resident_scenario import frozen_check
from suites.frontend.bpu.mbtb.case.resident_scenario import snapshot


def feedback(vector, metadata):
    return MbtbBatchTraining(vector.pc, deepcopy(metadata), (
        MbtbBranchFeedback(vector.target, 1, vector.position, vector.branch_type, mispredict=1),))

async def check_case(agent, coverage, align, bank, owner, phase, mode):
    sequence = 1 + align * 16 + bank * 8 + owner * 4 + int(phase == 'pending_second') * 2 + int(mode == 'flow')
    await agent.reset()
    first = BranchVector(0x40001000 + (bank << 5), 0x40009340, 1 + 16 * align, 3)
    second = replace(first, pc=first.pc + 0x80, target=first.target + 0x100)
    # DefaultConfig has four physical ways and a per-align-bank LRU array
    # indexed by PC[13:6]. The logical ``owner`` dimension chooses which reset
    # recency the scenario exercises: untounched cells allocate the LRU way 3,
    # while one primer per shared replacement cell makes way 2 the victim.
    primers = tuple(replace(vector, pc=vector.pc + 0x800, position=vector.position + 1,
                            target=vector.target + 0x800) for vector in (first, second))
    # The target replacer cell has one prior cold allocation, so the retained
    # record owns way 3.  The two stale rewrites are nominated to ways 2 and 1
    # by that cell's LRU, but their key matches the pending owner row, which is
    # where the correction is merged and written back.
    physical_owner = 3
    request_ways = (2, 1)
    if owner == 1:
        # Primers share each target cell's replacement state through the
        # internal-bank bit, which is not part of the replacer index.
        for vector in (first, second):
            primer = replace(vector, pc=vector.pc ^ 0x20, target=vector.target + 0x800,
                             position=vector.position + 1)
            cold = await agent.predict(primer.pc)
            assert_miss(cold)
            await agent.train_burst((feedback(primer, cold.meta_entries),))
    cold_first = await agent.predict(first.pc)
    cold_second = await agent.predict(second.pc)
    assert_miss(cold_first)
    assert_miss(cold_second)
    captured = [await agent.predict(second.pc) for _ in range(2)]
    for prediction in captured:
        require_mbtb_shadow_cold_metadata(prediction.meta_entries)
    # Sentinel reads must address a set that is never trained.  Keep the
    # blocked sentinel in the same internal bank as the writes so it stalls
    # SRAM writeback, and flip the internal-bank bit for the flow sentinel.
    blocked_pc = first.pc + 0x1000
    flow_pc = blocked_pc ^ 0x20
    sentinel = {pc: snapshot(await agent.predict(pc)) for pc in (blocked_pc, flow_pc)}
    async with agent.observe_entry_shadow() as shadows:
        async with agent.observe_entry_activity() as setup:
            lookups = [agent.submit_predict(blocked_pc, expected=frozen_check(sentinel[blocked_pc]))
                       for _ in range(READ_WINDOW)]
            # Both entry writes target the same internal bank; the single
            # write-buffer port retires the second four ticks later.
            setup_activity = expected_mbtb_entry_keys_activity((first.pc, second.pc), first.position,
                physical_owner, (first.target, second.target), 'blocked',
                writeback_offsets=(2, 8))
            await agent.train_entry_during_predictions_checked(
                (feedback(first, cold_first.meta_entries), feedback(second, cold_second.meta_entries)),
                lookups, setup, expected_activity=setup_activity, mode='blocked')
            for transfer in lookups:
                await transfer
            # Public reads also retire the two pending writes after pressure.
            prepared_first = await agent.predict(first.pc)
            prepared_second = await agent.predict(second.pc)
            assert_vector_hit(prepared_first, first)
            assert_vector_hit(prepared_second, second)
            base = align * (MAIN_WAYS + 1)
            first_way, second_way = matching_way(prepared_first, first), matching_way(prepared_second, second)
            assert first_way == second_way and base <= first_way < base + MAIN_WAYS
            assert matching_counter(prepared_first, first) == matching_counter(prepared_second, second) == 2
            (write_align, write_bank, set_idx), write_tag = mbtb_bank_coordinate(
                second.pc, second.position)
            depth = shadows[-1].value['banks'][write_align][write_bank][physical_owner][1]
            expected_slot = dict(valid=1, dirty=0, set_idx=set_idx,
                    tag=write_tag, branch_type=3, ras_action=0,
                    position=second.position % ALIGN_HALFWORDS,
                    carry=0, lower=second.target & ((1 << 20) - 1))
            agent.entry_scoreboard.check(expected=expected_slot, actual=depth,
                context=CheckContext(scoreboard='mbtb.shadow_depth', mode=ScoreboardMode.DIRECT,
                                     sequence_id=sequence, request=second,
                                     accepted_event=setup.feedback[0].event, observed_event=shadows[-1].event))
        if phase == 'pending_second':
            primer = replace(primers[1], target=primers[1].target + 0x400)
            current = await agent.predict(primer.pc)
            await agent.train_burst((feedback(primer, current.meta_entries),))
            primer_way = matching_way(await agent.predict(primer.pc), primer)
            assert base <= primer_way < base + MAIN_WAYS
            # DefaultConfig has four ways and a 32-position fetch block.  A
            # second key in the same internal bank is expected to reuse the
            # retained owner way, occupying the next service depth; it is not
            # forced into a different physical way as in the old two-way build.
            assert primer_way == first_way
        before = [snapshot(await agent.predict(vector.pc)) for vector in (first, second)]
        targets = mbtb_retarget_targets(second.pc, second.target, 'fit_overflow')
        expected_activity = expected_mbtb_shadow_activity(
            second.pc, second.position, physical_owner, targets, mode, phase,
            request_ways=request_ways,
            writeback_offsets=(2,) if mode == 'blocked' else (6, 10))
        expected_states = expected_mbtb_depth_one_states(
            before, align, physical_owner, targets, request_ways)
        transactions = tuple(feedback(replace(second, target=target), prediction.meta_entries)
                             for target, prediction in zip(targets, captured, strict=True))
        case = dict(align=align, bank=bank, owner=owner, physical_owner=physical_owner,
                    phase=phase, mode=mode,
                    depth_before=depth, expected_slot=expected_slot, expected_activity=expected_activity,
                    integrated_ftq_reachability_proven=False)
        dimensions = dict(align=align, bank=bank, owner=owner, phase=phase, mode=mode)
        coverage.sample(dict(dimensions, status="prepared"))
        async with agent.observe_entry_activity() as trace:
            read_pc = blocked_pc if mode == 'blocked' else flow_pc
            lookups = [agent.submit_predict(read_pc, expected=frozen_check(sentinel[read_pc]))
                       for _ in range(READ_WINDOW)]
            await agent.train_entry_during_predictions_checked(transactions, lookups, trace,
                expected_activity=expected_activity, mode=mode)
            for transfer in lookups:
                await transfer
            case['actual_activity'] = summarize_mbtb_entry_activity(trace.frames, trace.feedback, lookups, mode)
        case['depth_after'] = shadows[-1].value['banks'][write_align][write_bank][physical_owner][1]
        final_slot = dict(expected_slot, carry=1, lower=targets[-1] & ((1 << 20) - 1))
        agent.entry_scoreboard.check(expected=final_slot, actual=case['depth_after'],
            context=CheckContext(scoreboard='mbtb.shadow_depth', mode=ScoreboardMode.DIRECT,
                                 sequence_id=sequence, request=transactions,
                                 accepted_event=trace.feedback[0].event, observed_event=shadows[-1].event))
        transfers = [agent.submit_predict(vector.pc, expected=defined_depth_check(expected))
                     for vector, expected in zip((first, second), expected_states, strict=True)]
        await agent.drain_predictions()
        for transfer in transfers:
            await transfer
        coverage.sample(dict(dimensions, status="updated"))
        reverse = [agent.submit_predict(vector.pc, expected=defined_depth_check(expected))
                   for vector, expected in reversed(tuple(zip((first, second), expected_states, strict=True)))]
        await agent.drain_predictions()
        for batch in (transfers, reverse):
            for transfer in batch:
                await transfer
                assert transfer.completed_event.tick - transfer.accepted_event.tick == 4
            assert batch[1].accepted_event.tick - batch[0].accepted_event.tick == 2
        coverage.sample(dict(dimensions, status="revisited"))
        case['public_state_checked'] = True
        return case
