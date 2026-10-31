"""Target changes reach multi-provider update paths without a bank sweep."""
from dataclasses import asdict
import json

from toffee import CheckContext, Scoreboard, ScoreboardMode
from suites.frontend.bpu.bpu.checker.ittage import check_coherent_target, check_metadata
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.coverage.ittage import feedback_coverage, write_feedback_coverage
from suites.frontend.bpu.bpu.model.ittage import IttageContextModel
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback

PC, POSITION = 0x40000800, 4
TARGET_A, TARGET_B, TARGET_C = 0x40002000, 0x40004000, 0x40006000
TARGETS = (TARGET_A, TARGET_B, TARGET_C, TARGET_C, TARGET_C,
           TARGET_B, TARGET_B, TARGET_B, TARGET_B, TARGET_B,
           TARGET_A, TARGET_A, TARGET_A)


async def check_target_feedback(agent, root, *, targets=TARGETS, diagnostics=None,
                                region_checker=None, coherent_checker=None):
    targets = tuple(targets)
    if not targets or any(type(target) is not int or not 0 <= target < 1 << 49 for target in targets):
        raise ValueError('target feedback requires nonempty unsigned49 halfword targets')
    model, board, coverage = IttageContextModel(), Scoreboard('bpu.ittage_target_feedback'), feedback_coverage()
    await agent.reset(PC)
    cold = await agent.next_transaction(start_pc=PC)
    await agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
                                    sc=False, ras=False, ittage=True, settle=True)
    current = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    check_metadata(board, model, current, phase='cold')
    for step, target in enumerate(targets):
        # Correctness and feedback flags come from the model, not DUT targets.
        mispredict = int(model.target() != target)
        feedback = BpuBatchTraining(PC, current.meta.resolve,
            (BpuBranchFeedback(POSITION, target, branch_type=3, taken=1, mispredict=mispredict),))
        operations = model.advance(current.meta.resolve['ittage']['allocate'], target,
                                   mispredict=mispredict)
        if region_checker is not None:
            region_checker.plan_feedback(feedback)
        await agent.train_batch_with_prediction_pause(feedback)
        current = await revisit_from_redirect(agent, PC, cold.meta.redirect)
        if region_checker is not None:
            region_checker.raise_failure()
        try:
            check_metadata(board, model, current, phase=f'feedback-{step}')
        except Exception as error:
            if diagnostics is not None:
                # One semantic failure snapshot, not a per-cycle trace.
                (diagnostics / 'ittage-target-feedback-failure.json').write_text(json.dumps(dict(
                    failure=repr(error), step=step, feedback=asdict(feedback),
                    expected_metadata=model.metadata(), observed_transaction=asdict(current),
                    operations=sorted(operations), public_feedback_only=True,
                    region_observation=None if region_checker is None else region_checker.diagnostics(),
                    coherent_observation=None if coherent_checker is None else coherent_checker.summary(),
                    full_FTQ_legality_proven=False), indent=2) + '\n')
            raise
        wanted = model.target()
        context = CheckContext(board.name, ScoreboardMode.DIRECT,
            sequence_id=step, request=dict(expected_target=wanted, feedback_target=target))
        if coherent_checker is not None:
            check_coherent_target(board, coherent_checker, current, wanted, target, POSITION, context)
        else:
            correction = await agent.correction_for(current, target=wanted)
            board.check(expected=True, actual=correction is not None, context=context)
            if wanted != target:
                board.check(expected=(0, 1), actual=(correction.s2_override, correction.s3_override), context=context)
        for operation in operations | {'public_target_checked'}:
            coverage.sample(dict(operation=operation))
    coverage.assert_coverage(100.0)
    write_feedback_coverage(coverage, root)
    return dict(checks=board.status, operations=coverage.report())
