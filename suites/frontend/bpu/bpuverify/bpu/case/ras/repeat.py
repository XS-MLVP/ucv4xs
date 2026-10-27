"""Real repeated self-calls, with older accepted pipeline work fully drained.

The test owns intent only. Static ports, PulseDriver and @on monitoring remain
in the unchanged admitted retirement extension. No constructed SSP/tosw,
native-state initialization, private stream queue or testcase edge is used.
"""
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.case.ras.common import revisit_from_redirect
from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.case.ras.retirement import return_address

CALL_PC = 0x40018000
POSITION = 15
REQUESTED = (9, 10)


def expected_repeat_state(count):
    """Closed-form independent boundary oracle, not sampled native state."""
    if type(count) is not int or not 1 <= count <= 13:
        raise ValueError('bounded repeated-call burst must contain 1..13 calls')
    head = 1 if count <= 8 else 2
    address = return_address(CALL_PC, POSITION)
    cells = [dict(address=0, counter=0) for _ in range(16)]
    cells[1] = dict(address=address, counter=min(count - 1, 7))
    if count > 8:
        cells[2] = dict(address=address, counter=count - 9)
    return dict(head=head, cells=cells)


async def pause_and_collect(retirement, collected, boundary, requested):
    """Stop younger acceptance, retain and associate every older S3 transfer."""
    agent, checker = retirement.agent, retirement.checker
    await agent.set_ready(prediction=False, meta=True)
    await retirement.coherent.drain()
    retirement.phr.raise_failure()
    checker.raise_failure()
    candidates = list(collected) + [item for item in retirement.phr.association.completed
        if item.prediction_tick > boundary]
    candidates.sort(key=lambda item: item.meta_tick)
    ticks = [item.meta_tick for item in candidates]
    checker.check(len(ticks), len(set(ticks)), phase='no-duplicate-drained-transfer')
    checker.check(True, requested <= len(candidates) <= 13, phase='bounded-speculative-burst')
    checker.check([CALL_PC] * len(candidates), [item.meta.perf.start_pc for item in candidates],
                  phase='all-drained-program-PCs')
    spec_ticks = [row['tick'] for row in checker.records
        if row['tick'] > boundary and row['spec']['valid'] and row['spec']['enable']]
    checker.check(ticks, spec_ticks, phase='every-post-redirect-speculation-retired')
    for item in candidates:
        checker.check(1, mbtb_meta_for_position(item, POSITION)[1]['rawHit'],
                      phase='trained-self-call-source')
    return candidates


async def run_repeated_calls(agent, requested):
    if type(requested) is not int or requested not in REQUESTED:
        raise ValueError('requested repeated-call counts are 9 and 10')
    async with BpuRetirement(agent) as retirement:
        await agent.reset(CALL_PC)
        initial = await agent.next_transaction(start_pc=CALL_PC)
        await agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
            ittage=False, ras=False, mbtb=True, settle=True)
        cold = await revisit_from_redirect(agent, CALL_PC, initial.meta.redirect)
        assert cold.prediction.taken == 0
        await agent.train(BpuTraining(CALL_PC, POSITION, CALL_PC, cold.meta.resolve,
            branch_type=2, ras_action=2))
        await agent.configure_predictors(ras=True, settle=True)
        boundary = await agent.redirect(BpuRedirect(CALL_PC, cold.meta.redirect))
        collected = [await agent.next_transaction(start_pc=CALL_PC, after_tick=boundary)
                     for _ in range(requested)]
        transactions = await pause_and_collect(retirement, collected, boundary, requested)
        requests = await retirement.retire_many([(item, 2) for item in transactions])
        actual_count = len(requests)
        for index, applied in enumerate(retirement.checker.applied, 1):
            retirement.checker.check(expected_repeat_state(index), applied['expected'],
                tick=applied['tick'], phase='closed-form-every-repeat-boundary')
        retirement.checker.check(expected_repeat_state(actual_count),
            retirement.checker.reference.native(), phase='repeat-final-closed-form')
        accepted = retirement.checker.accepted
        retirement.checker.check([2] * (actual_count - 1),
            [right['tick'] - left['tick'] for left, right in zip(accepted, accepted[1:])],
            phase='consecutive-repeat-retirement')
        result = retirement.report()
        result.update(requested_calls=requested, actual_calls=actual_count,
            redirect_boundary=boundary, call_pc=CALL_PC, position=POSITION,
            program=[dict(pc=CALL_PC, target=CALL_PC, branch_type=2, action=2)] * actual_count,
            all_post_redirect_speculations_retired=True, younger_acceptance_paused=True,
            repeat_increment_and_saturation_split_observed=True,
            return_decrement_or_full_queue_reuse_covered=False,
            exact_speculation_source_ticks=[item.meta_tick for item in transactions])
        return result
