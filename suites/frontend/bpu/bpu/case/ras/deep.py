"""Bounded integrated call chains; sixteen calls exercise committed slot wrap."""
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_meta_for_position
from suites.frontend.bpu.bpu.case.ras.common import revisit_from_redirect
from suites.frontend.bpu.bpu.env.ras.retirement import BpuRetirement

POSITION = 15


def program(depth):
    if type(depth) is not int or depth not in (4, 7, 8, 15, 16):
        raise ValueError('qualified chain depths are 4, 7, 8, 15 and 16')
    calls = tuple(0x40010800 + 0x40 * index for index in range(depth))
    body = 0x40012000
    returns = depth if depth < 16 else 15
    # Sixteen real calls evict only the initial sentinel in the bounded model.
    # Do not fabricate an empty sixteenth return or claim a bottom-stack model.
    return_pcs = (body, *(pc + 16 for pc in reversed(calls[depth - returns + 1:])))
    assert len(return_pcs) == returns
    call_cases = tuple((pc, calls[index + 1] if index + 1 < depth else body, 2, 2)
                       for index, pc in enumerate(calls))
    return_cases = tuple((pc, 0x40013000, 3, 1) for pc in return_pcs)
    return calls, call_cases + return_cases


async def run_chain(agent, depth):
    calls, cases = program(depth)
    async with BpuRetirement(agent) as retirement:
        await agent.reset(calls[0])
        initial = await agent.next_transaction(start_pc=calls[0])
        await agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
            ittage=False, ras=False, mbtb=True, settle=True)
        cold_first = await revisit_from_redirect(agent, calls[0], initial.meta.redirect)
        cold = cold_first
        for index, (pc, target, branch_type, action) in enumerate(cases):
            assert cold.prediction.start_pc == pc and cold.prediction.taken == 0
            await agent.train(BpuTraining(pc, POSITION, target, cold.meta.resolve,
                branch_type=branch_type, ras_action=action))
            if index + 1 < len(cases):
                cold = await revisit_from_redirect(agent, cases[index + 1][0], cold.meta.redirect)
        await agent.configure_predictors(ras=True, settle=True)
        boundary = await agent.redirect(BpuRedirect(calls[0], cold_first.meta.redirect))
        operations = []
        for pc, _, _, action in cases:
            transaction = await agent.next_transaction(start_pc=pc, after_tick=boundary)
            assert mbtb_meta_for_position(transaction, POSITION)[1]['rawHit'] == 1
            operations.append((transaction, action))
        requests = await retirement.retire_many(operations)
        retirement.checker.check([item[3] for item in cases], [item['action'] for item in requests],
                                 phase='deep-program-order')
        retirement.checker.check(0 if depth < 16 else 1, retirement.checker.reference.head,
                                 phase='bounded-chain-final-head')
        accepted = retirement.checker.accepted
        retirement.checker.check([2] * (len(accepted) - 1),
            [b['tick'] - a['tick'] for a, b in zip(accepted, accepted[1:])],
            phase='consecutive-deep-retirement')
        result = retirement.report()
        result.update(depth=depth, program=[dict(pc=pc, target=target, branch_type=branch_type, action=action)
            for pc, target, branch_type, action in cases],
            retained_evictions=[dict(address=group.address, counter=group.counter, slot=group.slot)
                               for group in retirement.checker.reference.evicted],
            bottom_or_empty_return_modeled=False, repeat_counter_boundaries_covered=False)
        return result
