"""Both conditional branches resolve NT; opposite base predictions make useful observable."""
from suites.frontend.bpu.bpu.case.definitions import PC, POSITION, LATER_POSITION, EARLIER_TARGET, LATER_TARGET
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect, mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.tage.semantic import TageSemanticComponentChecker
from suites.frontend.bpu.bpu.coverage.tage.learning import RULES
from suites.frontend.bpu.bpu.model.selection import Branch, Kind, early, middle, final, middle_repair, final_repair
from suites.frontend.bpu.bpu.monitor.tage.semantic import TageSemanticComponentMonitor
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback, BpuTraining


def qualified_learning_event(accepted, slots):
    if len(accepted) != 1 or slots != [(accepted[0][0], (None, POSITION, None, None, None, None, LATER_POSITION, None))]:
        return False
    request = accepted[0][1]
    return (request.pc == PC and len(request.branches) == 2
        and len({(branch.hint.table, branch.hint.way) for branch in request.branches}) == 2 and all(
        (branch.position, branch.kind, branch.taken, branch.matched, branch.mispredict, branch.base_counter) == (
            position, 1, False, True, False, 2)
        and branch.hint.provider and not branch.hint.alternate and branch.hint.use_provider
        and branch.hint.counter == 2 and branch.hint.useful == 0 and branch.hint.alternative
        for branch, position in zip(request.branches, (POSITION, LATER_POSITION), strict=True)))


async def check_sparse_learning(agent, coverage):
    reference = TageSemanticComponentChecker()
    monitor = TageSemanticComponentMonitor(agent)
    monitor.start(reference)
    failed = False
    try:
        await agent.reset(PC)
        initial = await agent.next_transaction(start_pc=PC)
        await agent.configure_predictors(ubtb=False, abtb=False, tage=True,
                                         sc=False, ittage=False, ras=False, settle=True)
        anchor = initial.meta.redirect

        async def query(*, tage=True, positions=(POSITION, LATER_POSITION)):
            source = await revisit_from_redirect(agent, PC, anchor)
            reference.raise_failure()
            if tage:
                for position in positions:
                    reference.source_expected(source, position)
            return source

        source = await query(positions=())
        known = []
        for position, target in ((POSITION, EARLIER_TARGET), (LATER_POSITION, LATER_TARGET)):
            # Allocate the MainBTB record first, then let its first genuine
            # wrong taken-base feedback allocate a negative TAGE provider.
            # Reversing an already positive provider would add an agreeing
            # alternate and would NOT satisfy the useful-increment condition.
            await agent.train(BpuTraining(PC, position, target, source.meta.resolve, branch_type=1))
            known.append(position)
            source = await query(positions=known)
            assert reference.source_expected(source, position)['hasProvider'] == 0
            await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve,
                (BpuBranchFeedback(position, target, 1, taken=0, mispredict=1),)))
            source = await query(positions=known)
            assert reference.source_expected(source, position)['providerTakenCtr_value'] == 3
            await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve,
                (BpuBranchFeedback(position, target, 1, taken=0),)))
            source = await query(positions=known)
            assert reference.source_expected(source, position)['hasAlt'] == 0
        assert [reference.source_expected(source, p)['providerTakenCtr_value']
                for p in (POSITION, LATER_POSITION)] == [2, 2]
        await agent.configure_predictors(tage=False, settle=True)
        for phase in range(3):
            source = await query(tage=False)
            await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve,
                (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=1, mispredict=int(phase < 2)),)))
        # Strengthening the later TAGE provider also decremented its MainBTB
        # counter to zero. Two later-taken trajectories are needed; restore
        # the earlier base between them so both final base counters are two.
        for phase in range(2):
            source = await query(tage=False)
            await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve, (
                BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0, mispredict=1),
                BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=1))))
            if phase == 0:
                source = await query(tage=False)
                await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve,
                    (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=1),)))
        await agent.configure_predictors(tage=True, settle=True)
        source = await query()
        base_counters = [mbtb_counter_for_position(source, p) for p in (POSITION, LATER_POSITION)]
        assert base_counters == [2, 2], base_counters
        before = [reference.source_expected(source, p) for p in (POSITION, LATER_POSITION)]
        assert [m['providerTakenCtr_value'] for m in before] == [2, 2]
        assert [m['providerUsefulCtr_value'] for m in before] == [0, 0]
        assert len({(m['providerTableIdx'], m['providerWayIdx']) for m in before}) == 2
        candidates = (Branch(POSITION, EARLIER_TARGET, Kind.CONDITIONAL),
                      Branch(LATER_POSITION, LATER_TARGET, Kind.CONDITIONAL))
        s1, s2 = early(PC), middle(PC, candidates, (False, False))
        s3 = final(PC, candidates, (False, False), (None, None))
        assert not middle_repair(s1, s2) and not final_repair(s1, s2, s3, corrected_middle=False)
        assert (source.prediction.target, source.prediction.taken, source.prediction.position) == (
            s3.branch.target, int(s3.branch.taken), s3.branch.position)
        branches = [None] * 8
        branches[1] = BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0)
        branches[6] = BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=0)
        first_tick = reference.input_tick
        try:
            await agent.train_batch_with_prediction_pause(BpuBatchTraining(PC, source.meta.resolve, tuple(branches)))
            reference.raise_failure()
        finally:
            accepted = [(tick, request) for tick, request in reference.accepted_feedback if tick > first_tick]
            slots = [(tick, values) for tick, values in reference.resolve_slots if tick > first_tick]
            if qualified_learning_event(accepted, slots):
                for rule in RULES:
                    coverage.record('reached', rule, accepted_tick=accepted[0][0], resolve_slots=(1, 6))
        assert qualified_learning_event(accepted, slots), (accepted, slots)
        observed = await query()
        after = [reference.source_expected(observed, p) for p in (POSITION, LATER_POSITION)]
        assert [m['providerTakenCtr_value'] for m in after] == [1, 1]
        useful_values = [m['providerUsefulCtr_value'] for m in after]
        assert useful_values == [1, 1], useful_values
        assert [(m['providerTableIdx'], m['providerWayIdx']) for m in after] == [
            (m['providerTableIdx'], m['providerWayIdx']) for m in before]
        for rule in RULES:
            coverage.record('checked', rule, metadata_tick=observed.meta_tick)
    except BaseException:
        failed = True
        raise
    finally:
        await monitor.aclose()
        if not failed:
            reference.raise_failure()
