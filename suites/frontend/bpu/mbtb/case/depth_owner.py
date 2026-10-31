"""Two real retained keys and an older source; normal transactions only."""
from copy import deepcopy
from dataclasses import replace

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.models.configuration import ALIGN_HALFWORDS, MAIN_ROWS
from suites.frontend.bpu.mbtb.case.definitions import BranchVector
from suites.frontend.bpu.mbtb.case.depth_scenario import feedback
from suites.frontend.bpu.mbtb.case.resident_scenario import frozen_check, snapshot
from suites.frontend.bpu.mbtb.case.semantic import branch_state
from suites.frontend.bpu.mbtb.checker.assertions import assert_miss
from suites.frontend.bpu.mbtb.checker.depth import defined_depth_check
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback, observed_mbtb_feedback
from suites.frontend.bpu.mbtb.model.depth import expected_depth_target_state
from suites.frontend.bpu.mbtb.model.entry_keys import entry_key_coordinate
from suites.frontend.bpu.mbtb.model.entry_keys import entry_key_tag
from suites.frontend.bpu.mbtb.model.entry_keys import expected_mbtb_entry_keys_activity
from suites.frontend.bpu.mbtb.model.shadow import require_mbtb_shadow_cold_metadata
from suites.frontend.bpu.mbtb.monitor.entry import ENTRY_FIELDS
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback, MbtbTraining


def slot_for(vector):
    # Same MainBTB coordinate geometry as the independent semantic model.
    _, _, set_idx = entry_key_coordinate(vector.pc)
    return dict(valid=1, dirty=0, set_idx=set_idx, tag=entry_key_tag(vector.pc),
        branch_type=vector.branch_type, ras_action=0,
        position=vector.position, carry=0, lower=vector.target & ((1 << 20) - 1))


def transfers(frames, direction, *, bank):
    # Walk the real internal bank of this scenario; the monitor exposes every
    # align bank and internal bank, and the first fetch is not in bank 0.
    result = []
    for frame in frames:
        for align in range(2):
            for way, port in enumerate(frame.value['banks'][align][bank]):
                if port[f'{direction}_valid'] and (direction == 'write' or port['read_ready']):
                    result.append((way, {field: port[f'{direction}_{field}'] for field, _ in ENTRY_FIELDS}))
    return result


async def check_depth_owner(agent, coverage, *, stale):
    if type(stale) is not bool:
        raise ValueError('depth owner source selection must be a semantic bool')
    first = BranchVector(0x40001020, 0x40009340, 1, 3)
    bank = (first.pc >> 5) & 3
    second = replace(first, pc=first.pc + 0x80, target=first.target + 0x100)
    peer = BranchVector(second.pc, second.target + 0x400, 0, 1)
    changed = replace(second, target=second.target + 0x100)
    board = Scoreboard('mbtb.second-depth-owner')
    context = CheckContext(board.name, ScoreboardMode.DIRECT,
        request=dict(first=first, second=second, peer=peer, new_target=changed.target, stale=stale))
    check = lambda expected, actual: board.check(expected=expected, actual=actual, context=context)
    await agent.reset()
    cold = [await agent.predict(vector.pc) for vector in (first, second)]
    for prediction in cold:
        assert_miss(prediction)
        require_mbtb_shadow_cold_metadata(prediction.meta_entries)
    original = deepcopy(cold[1].meta_entries)
    blocked_pc = first.pc + 128
    sentinel = snapshot(await agent.predict(blocked_pc))

    async with agent.observe_entry_shadow() as shadows:
        async with agent.observe_entry_activity() as setup:
            # Two accepted allocations plus their two-stage request path.
            reads = 4
            lookups = [agent.submit_predict(blocked_pc, expected=frozen_check(sentinel)) for _ in range(reads)]
            # Both keys land in way 3 of one internal bank; the second entry
            # write retires four entry-write ticks after the first because a
            # single write-buffer port serializes them.
            expected = expected_mbtb_entry_keys_activity((first.pc, second.pc), 1, 3,
                (first.target, second.target), 'blocked', reads=reads,
                writeback_offsets=(2, 8))
            await agent.train_entry_during_predictions_checked(
                tuple(feedback(vector, source.meta_entries) for vector, source in zip((first, second), cold, strict=True)),
                lookups, setup, expected_activity=expected, mode='blocked')

        # Add and age a genuine earlier conditional while retaining the
        # indirect record at the second shadow depth in the other owner.
        current = await agent.predict(second.pc)
        # Capture the real owner way from the prepared public prediction; the
        # DefaultConfig replacer order differs from the old fixed policy.
        owner = branch_state(current, 1, 3)[0]
        check((owner, second.target, 1, 2), branch_state(current, 1, 3))
        await agent.train(MbtbTraining(peer.pc, peer.target, 1, 0, 1, current.meta_entries))
        for _ in range(2):
            current = await agent.predict(second.pc)
            counter = branch_state(current, 0, 1)[3]
            await agent.train(MbtbTraining(peer.pc, peer.target, 0, 0, 1,
                current.meta_entries, mispredict=int(counter >= 2)))
        current = await agent.predict(second.pc)
        await agent.train_batch(MbtbBatchTraining(second.pc, deepcopy(current.meta_entries), (
            MbtbBranchFeedback(peer.target, 0, 0, 1),
            MbtbBranchFeedback(second.target, 1, 1, 3),
        )))
        before = [snapshot(await agent.predict(vector.pc)) for vector in (first, second)]
        current = await agent.predict(second.pc)
        peer_way = branch_state(current, 0, 1)[0]
        check((peer_way, peer.target, 0, 0), branch_state(current, 0, 1))
        check((owner, second.target, 1, 2), branch_state(current, 1, 3))
        check(slot_for(first), shadows[-1].value['banks'][0][bank][owner][0])
        check(slot_for(second), shadows[-1].value['banks'][0][bank][owner][1])
        check(original, cold[1].meta_entries)

        metadata = deepcopy(original if stale else current.meta_entries)
        request = MbtbBatchTraining(second.pc, metadata, (
            MbtbBranchFeedback(peer.target, 0, 0, 1),
            MbtbBranchFeedback(changed.target, 1, 1, 3, mispredict=1),
        ))
        frozen_metadata = deepcopy(request.meta_entries)
        intended = expected_mbtb_feedback(request, branch_count=len(agent.ports.training.bits.branches))
        expected_payload = {key: value for key, value in slot_for(changed).items() if key not in ('valid', 'dirty')}
        expected_offer = (0 if stale else owner, expected_payload)
        rule = 'stale-source-depth-owner-with-negative-peer' if stale else 'fresh-source-depth-owner-control'
        failure = None
        async with agent.observe_entry_activity() as trace:
            try:
                await agent.train_batch(request)
            except Exception as error:
                failure = error
        accepted = [observed_mbtb_feedback(frame.value) for frame in trace.feedback]
        proposals, services = (transfers(trace.frames, 'write', bank=bank),
                              transfers(trace.frames, 'read', bank=bank))
        # Do not replace the first independent-model failure with a secondary
        # preparation assertion. Reached credit still requires the full offer.
        qualified = accepted == [intended] and proposals == [expected_offer]
        if qualified:
            coverage.record('reached', rule, owner=owner, depth=1, peer_counter=0,
                            requested_way=expected_offer[0], actual_service=services)
        if failure is not None:
            raise failure
        check([intended], accepted)
        check([expected_offer], proposals)
        check([(owner, expected_payload)], services)
        check(original, cold[1].meta_entries)
        check(frozen_metadata, request.meta_entries)
        if not stale:
            check(slot_for(first), shadows[-1].value['banks'][0][bank][owner][0])
            check(slot_for(changed), shadows[-1].value['banks'][0][bank][owner][1])
            expected_states = expected_depth_target_state(before, 0, owner, changed.target)
        else:
            # A stale source must not create the new depth record at all: the
            # retained depth still describes the original prepared entry.
            check(slot_for(first), shadows[-1].value['banks'][0][bank][owner][0])
            expected_states = before
        for vector, expected in zip((first, second), expected_states, strict=True):
            agent.submit_predict(vector.pc, expected=defined_depth_check(expected))
        await agent.drain_predictions()
        check((peer_way, peer.target, 0, 0), branch_state(await agent.predict(second.pc), 0, 1))
        coverage.record('checked', rule, owner=owner, depth=1, peer_counter=0, full_consumers=True)
