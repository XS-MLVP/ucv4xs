"""Natural BPU nested program plus public, consecutive retirement beats."""
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.model.sc.metadata import mbtb_meta_for_position
from bpuverify.bpu.case.ras.common import revisit_from_redirect
from bpuverify.bpu.env.ras.retirement import BpuRetirement

OUTER, INNER, BODY = 0x40000800, 0x40000900, 0x40000a00
INNER_RETURN, OUTER_RETURN = INNER + 16, OUTER + 16
POSITION = 15


async def run_nested(agent):
    async with BpuRetirement(agent) as retirement:
        await agent.reset(OUTER)
        initial = await agent.next_transaction(start_pc=OUTER)
        await agent.configure_predictors(ubtb=False, abtb=False, tage=False, sc=False,
            ittage=False, ras=False, mbtb=True, settle=True)
        cold_outer = await revisit_from_redirect(agent, OUTER, initial.meta.redirect)
        cases = ((OUTER, INNER, 2, 2), (INNER, BODY, 2, 2),
                 (BODY, 0x40000b00, 3, 1), (INNER_RETURN, 0x40000c00, 3, 1))
        cold = cold_outer
        for index, (pc, target, branch_type, action) in enumerate(cases):
            assert cold.prediction.start_pc == pc and cold.prediction.taken == 0
            await agent.train(BpuTraining(pc, POSITION, target, cold.meta.resolve,
                branch_type=branch_type, ras_action=action))
            if index + 1 < len(cases):
                cold = await revisit_from_redirect(agent, cases[index + 1][0], cold.meta.redirect)
        await agent.configure_predictors(ras=True, settle=True)
        boundary = await agent.redirect(BpuRedirect(OUTER, cold_outer.meta.redirect))
        operations = []
        for pc, action in ((OUTER, 2), (INNER, 2), (BODY, 1), (INNER_RETURN, 1)):
            transaction = await agent.next_transaction(start_pc=pc, after_tick=boundary)
            assert mbtb_meta_for_position(transaction, POSITION)[1]['rawHit'] == 1
            operations.append((transaction, action))
        requests = await retirement.retire_many(operations)
        retirement.checker.check([2, 2, 1, 1], [row['action'] for row in requests], phase='program-order')
        retirement.checker.check(0, retirement.checker.reference.head, phase='nested-stack-restored')
        accepted = retirement.checker.accepted
        retirement.checker.check([2, 2, 2], [b['tick'] - a['tick'] for a, b in zip(accepted, accepted[1:])],
                                 phase='consecutive-public-retirement-beats')
        return retirement.report()
