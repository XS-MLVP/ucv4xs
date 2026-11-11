"""Owned composition scenarios returning detached evidence, never infrastructure handles."""
import asyncio
from copy import deepcopy

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.early_direction import discover_negative_path
from suites.frontend.bpu.testbenches.bpu.checker.composition import BothLiveChecker
from suites.frontend.bpu.testbenches.bpu.checker.composition import CollisionChecker
from suites.frontend.bpu.testbenches.bpu.checker.composition import FieldTally
from suites.frontend.bpu.testbenches.bpu.checker.composition import HistoryIndexChecker
from suites.frontend.bpu.testbenches.bpu.checker.composition import SharedRedirectChecker
from suites.frontend.bpu.testbenches.bpu.checker.composition import discriminating_target
from suites.frontend.bpu.testbenches.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.testbenches.bpu.coverage.early_direction import EarlyDirectionCoverage
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.early_direction import early_direction_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.indirect_learning import indirect_program
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBatchTraining
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuBranchFeedback
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect


async def early_composition(agent, *, pc, probe):
    factories = {'main-ahead': BothLiveChecker, 'shared-redirect': SharedRedirectChecker,
                 'field-liveness': FieldTally}
    if probe not in factories:
        raise ValueError(f'unknown early composition probe: {probe!r}')
    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, pc)
    factory = factories[probe]
    async with early_direction_program(agent, pc, checks, checker_factory=factory) as program:
        await discover_negative_path(program, checks)
        checker = program.checker
        assert isinstance(checker, factory)
        checker.raise_failure()
        if probe == 'field-liveness':
            # Preserve the original tally cut, before the scope's final drain.
            report = dict(samples=checker.samples,
                expected_distinct={key: len(values) for key, values in checker.values.items()},
                actual_distinct={key: len(values) for key, values in checker.actuals.items()})
    # Scope exit must complete the existing stop/drain/finish contract. A copied
    # report cannot pay those obligations and must not escape a failed finish.
    if probe == 'main-ahead':
        report = dict(cycles=checker.both_compared, counts=dict(checker.counts))
    elif probe == 'shared-redirect':
        report = dict(cycles=checker.shared_redirect_cycles, post_redirect=checker.post_redirect_cycles,
                      counts=dict(checker.counts))
    return deepcopy(report)


async def redirect_training(agent, *, pc, distinguish_origin):
    coverage = EarlyDirectionCoverage('byte-tag-control')
    checks = EarlyDirectionChecks(coverage, pc)
    factory = HistoryIndexChecker if distinguish_origin else CollisionChecker
    async with early_direction_program(agent, pc, checks, checker_factory=factory) as program:
        anchor = await discover_negative_path(program, checks)
        checker = program.checker
        assert isinstance(checker, factory)
        assert not checker.collisions, (
            'the program already produced a collision; the co-launch below would be redundant',
            checker.collisions)
        transaction = BpuBatchTraining(pc, anchor.meta.resolve,
            (BpuBranchFeedback(2, pc, 1, taken=0, mispredict=1),))
        checker.plan_feedback(anchor, transaction)
        target = discriminating_target(checker.source_token(anchor), pc) if distinguish_origin else pc
        request = BpuRedirect(target, anchor.meta.redirect, cfi_pc=pc + 4)
        checker.plan_redirect(anchor, request)
        training = asyncio.create_task(agent.train_batch(transaction))
        try:
            await agent.redirect(request)
            await training
        finally:
            # The owner must not leave an orphan drive if recovery/checking
            # fails. Cancellation never turns an accepted beat into completion.
            if not training.done():
                training.cancel()
                try:
                    await training
                except asyncio.CancelledError:
                    pass
        await agent.set_ready(prediction=True, meta=True)
        if distinguish_origin:
            await program.observation.wait('post_collision_boundary_compared',
                lambda _: checker.awaiting is None, timeout_cycles=32)
        checker.raise_failure()
    return deepcopy(dict(collisions=checker.collisions, counts=dict(checker.counts)))


async def unpublished_ittage(agent, *, pc, position, target, coverage, evidence):
    """Keep the original lookup receipts through a late unpublished resolve."""
    async with indirect_program(agent, pc) as program:
        await agent.configure_predictors(ittage=False, settle=True)
        original = await program.capture_source(pc)
        original_meta = original.meta.resolve['ittage']
        assert original_meta['valid'] == 0
        evidence['original'] = deepcopy(dict(valid=original_meta['valid'],
            provider=original_meta['provider'], allocate=original_meta['allocate']))
        coverage.record('reached', 'unpublished-original-observed', valid=original_meta['valid'])
        coverage.record('checked', 'unpublished-original-observed')
        await agent.configure_predictors(ittage=True, settle=True)
        fresh = await program.capture_source(pc)
        fresh_meta = fresh.meta.resolve['ittage']
        assert fresh_meta['valid'] == 1
        evidence['fresh'] = deepcopy(dict(valid=fresh_meta['valid'],
            provider=fresh_meta['provider'], allocate=fresh_meta['allocate']))
        coverage.record('reached', 'late-feedback-does-not-learn-ittage', valid=original_meta['valid'])
        await program.resolve(original,
            BpuBranchFeedback(position, target, branch_type=3, taken=1, mispredict=1))
        coverage.record('reached', 'fresh-consumer-remains-cold')
        final = await program.capture_source(pc)
        final_meta = final.meta.resolve['ittage']
        assert final_meta['valid'] == 1
        assert final_meta['provider']['valid'] == 0, (
            'an unpublished original must not create an ITTAGE provider')
        coverage.record('checked', 'fresh-consumer-remains-cold')
        evidence['final'] = deepcopy(dict(valid=final_meta['valid'],
            provider=final_meta['provider'], allocate=final_meta['allocate']))
        program.checker.raise_failure()
