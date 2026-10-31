"""Genuine feedback builds valid S2/S3 not-taken direction repairs."""

from suites.frontend.bpu.runtime.trace import dump_trace
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from toffee import CheckContext
from toffee import ScoreboardMode
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.transaction.types import BpuTraining
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.assertions import revisit_from_redirect
from suites.frontend.bpu.bpu.checker.assertions import sc_meta_for_position
from suites.frontend.bpu.bpu.checker.assertions import tage_meta_for_position
from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.definitions import POSITION
from suites.frontend.bpu.bpu.case.definitions import EARLIER_TARGET
from suites.frontend.bpu.bpu.case.scenarios import prepare_two_tage_providers
from suites.frontend.bpu.bpu.case.scenarios import train_sc_feedback_with_tage_held
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.model.phr.model import subtract
from suites.frontend.bpu.bpu.coverage.phr.supplemental import DIRECTION_PHASES as PHASES
from suites.frontend.bpu.bpu.coverage.phr.supplemental import bpu_phr_direction_repair_coverage_model as coverage_model
from suites.frontend.bpu.bpu.coverage.phr.supplemental import write_bpu_phr_direction_repair_coverage as write_coverage


async def revisit_with_cadence(agent, observation, meta, *, mode):
    accepted_tick = await agent.redirect(BpuRedirect(PC, meta))
    if mode == 'backpressured':
        await observation.pause_after_s1(start_pc=PC, after_tick=accepted_tick)
    return await agent.next_transaction(start_pc=PC, after_tick=accepted_tick)


def check(checker, expected, actual, **request):
    checker.raise_failure()
    checker.scoreboard.check(expected=expected, actual=actual,
        context=CheckContext(scoreboard=checker.scoreboard.name,
            mode=ScoreboardMode.DIRECT, request=request))


async def prepare_taken_provider(agent, checker, *, stage):
    """Qualify a real taken branch; no fabricated redirect or resolve metadata."""
    if stage == 's3':
        prepared = await prepare_two_tage_providers(agent)
        return prepared.cold, prepared.single_provider
    await agent.reset(PC)
    cold = await agent.next_transaction(start_pc=PC)
    check(checker, 0, cold.prediction.taken, phase='enabled-cold-start', stage=stage)
    await agent.configure_predictors(ubtb=(stage == 's2'), abtb=False,
        tage=(stage == 's3'), sc=False, ittage=False, ras=False, settle=True)
    cold = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    await agent.train(BpuTraining(PC, POSITION, EARLIER_TARGET,
        cold.meta.resolve, branch_type=1))
    first = await revisit_from_redirect(agent, PC, cold.meta.redirect)
    check(checker, 2, mbtb_counter_for_position(first, POSITION), phase='taken-entry', stage=stage)
    return cold, first


async def check_override(agent, output, *, stage, mode='flowing'):
    if stage not in ('s2', 's3'):
        raise ValueError('override stage must be s2 or s3')
    if mode not in ('flowing', 'backpressured'):
        raise ValueError('unknown override cadence')
    checker = BpuPhrChecker(scope=dict(stage=stage, mode=mode, scenario='not-taken-direction-repair'))
    observation = agent.observe_phr(checker)
    coverage = coverage_model(stage, mode)
    failure, witnesses, preparation = None, [], {}
    try:
        async with observation:
            cold, taken = await prepare_taken_provider(agent, checker, stage=stage)
            preparation['cold'] = asdict(cold)
            preparation['taken'] = asdict(taken)
            if stage == 's2':
                # MicroBTB predicts always-taken; one genuine conditional NT
                # resolve decrements MainBTB's two-bit counter from 2 to 1.
                await agent.train(BpuTraining(PC, POSITION, EARLIER_TARGET,
                    taken.meta.resolve, branch_type=1, taken=0, mispredict=0))
            else:
                # The complete existing preparation leaves provider2/3. Train
                # the earlier provider through real feedback to a taken4,
                # while the later provider remains not-taken3.
                from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining
                current = await revisit_from_redirect(agent, PC, cold.meta.redirect)
                for expected in (3, 4):
                    await agent.train_batch_with_prediction_pause(BpuBatchTraining(
                        PC, current.meta.resolve,
                        (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=1),)))
                    current = await revisit_from_redirect(agent, PC, cold.meta.redirect)
                    check(checker, expected, tage_meta_for_position(current, POSITION)['providerTakenCtr_value'],
                        phase='prepare-taken-provider-by-real-feedback')
                await agent.configure_predictors(sc=True, settle=True)
                qualified = await revisit_from_redirect(agent, PC, cold.meta.redirect)
                preparation['sc_qualified'] = asdict(qualified)
                check(checker, 4, sc_meta_for_position(qualified, POSITION)['tageCtr'],
                    phase='sc-qualified-taken-provider')
                await train_sc_feedback_with_tage_held(agent, qualified,
                    (BpuBranchFeedback(POSITION, EARLIER_TARGET, 1, taken=0),), repetitions=32)
            window = len(checker.records)
            preparation['override_window_start_tick'] = checker.records[-1]['tick']
            checker.override_window_active = True
            restored = await revisit_with_cadence(agent, observation, cold.meta.redirect, mode=mode)
            preparation['restored'] = asdict(restored)
            await agent.set_ready(prediction=False, meta=True)
            await observation.drain()
            for index in range(window, len(checker.records) - 1):
                row = checker.records[index]
                request = row['boundary'][stage]
                if request['valid'] and request['start_pc'] == PC and not request['prediction']['taken']:
                    # The full independent checker already checked all 52 cells,
                    # all 76 fold registers, pending state and causal metadata.
                    next_row = checker.records[index + 1]
                    check(checker, subtract(request['meta']['pointer'], 2), row['state']['pointer'],
                        phase='speculative-taken-pointer-before-repair', stage=stage, mode=mode, tick=row['tick'])
                    check(checker, request['meta']['pointer'], next_row['state']['pointer'],
                        phase='not-taken-pointer-restoration', stage=stage, tick=row['tick'])
                    check(checker, dict(valid=1, taken=0, low=request['meta']['low']),
                        {key: next_row['state']['pending'][key] for key in ('valid', 'taken', 'low')},
                        phase='not-taken-pending-restoration', stage=stage, tick=row['tick'])
                    public = row['public_prediction']
                    check(checker, dict(start_pc=PC, target=PC + 16, taken=0, position=15,
                        s2_override=int(stage == 's2'), s3_override=int(stage == 's3')),
                        public['bits'], phase='public-not-taken-correction', stage=stage, mode=mode, tick=row['tick'])
                    check(checker, int(mode == 'flowing'), public['ready'],
                        phase='required-correction-backpressure', stage=stage, mode=mode, tick=row['tick'])
                    witnesses.append(dict(tick=row['tick'], request=deepcopy(request),
                        before_pointer=deepcopy(row['state']['pointer']),
                        next_state=deepcopy(next_row['state']), output=deepcopy(row['public_prediction'])))
            check(checker, True, bool(witnesses), phase='required-real-not-taken-override', stage=stage)
            if stage == 's2':
                check(checker, 1, restored.prediction.taken, phase='early-always-taken-control', stage=stage)
                check(checker, 1, mbtb_counter_for_position(restored, POSITION), phase='base-counter-not-taken', stage=stage)
            else:
                sc = sc_meta_for_position(restored, POSITION)
                check(checker, dict(tagePredValid=1, tageCtr=4, scPred=0, useScPred=1, sumAboveThres=1),
                    sc, phase='late-direction-correction-qualified', stage=stage)
            for phase in PHASES:
                coverage.sample(dict(checked=phase))
            coverage.assert_coverage(100.0)
            return checker.summary()
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        write_coverage(coverage, Path(output), stage, mode)
        dump_trace(Path(output, 'results/bpu', f'phr-override-{stage}-{mode}.json'), dict(
            stage=stage, mode=mode, failure=failure, trace=checker.records, witnesses=witnesses,
            preparation=preparation, accepted=observation.accepted,
            summary=None if failure else checker.summary(), formal_credit=False))
