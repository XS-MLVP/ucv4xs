"""Real valid taken repairs at pointer0, using a genuine NT fallthrough recovery.

PHR1566/1576 are the inner taken-pointer wrap arms, not the outer NT arms.
The input recovery comes from an earlier observed fetch block, whose final
halfword conditional falls through to the trained next block. Neither history
metadata nor any internal predictor state is fabricated or written.
"""

from bpuverify.common.env.trace import dump_trace
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from bpuverify.bpu.transaction.types import BpuTraining
from bpuverify.bpu.transaction.types import BpuBatchTraining
from bpuverify.bpu.transaction.types import BpuBranchFeedback
from bpuverify.bpu.transaction.types import BpuRedirect
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.assertions import tage_meta_for_position
from bpuverify.bpu.checker.assertions import sc_meta_for_position
from bpuverify.bpu.case.phr_direction_repair import check
from bpuverify.bpu.model.phr.model import subtract
from bpuverify.bpu.coverage.phr.supplemental import WRAP_PHASES as PHASES
from bpuverify.bpu.coverage.phr.supplemental import bpu_phr_taken_wrap_coverage_model as coverage_model
from bpuverify.bpu.coverage.phr.supplemental import write_bpu_phr_taken_wrap_coverage as write_coverage

ORIGIN = 0x40000800
DESTINATION = ORIGIN + 16
POSITION = 4
LATER_POSITION = 6
TARGET = DESTINATION + 0x200
LATER_TARGET = DESTINATION + 0x300


async def revisit(agent, observation, anchor, *, mode='flowing', arm=False):
    accepted_tick = await agent.redirect(BpuRedirect(DESTINATION, anchor,
        cfi_pc=ORIGIN + 15, taken=0, branch_type=1))
    if arm:
        observation.checker.wrap_window_active = True
    if mode == 'backpressured':
        await observation.pause_after_s1(start_pc=DESTINATION, after_tick=accepted_tick)
    return await agent.next_transaction(start_pc=DESTINATION, after_tick=accepted_tick)


async def prepare(agent, observation, checker, stage):
    await agent.reset(ORIGIN)
    origin = await agent.next_transaction(start_pc=ORIGIN)
    check(checker, dict(phrPtr=dict(flag=0, value=0), phrLowBits=0),
        origin.meta.redirect['phr'], phase='genuine-initial-pointer-zero')
    await agent.configure_predictors(ubtb=False, abtb=False,
        tage=(stage == 's3'), sc=False, ittage=False, ras=False, settle=True)
    cold = await revisit(agent, observation, origin.meta.redirect)
    check(checker, 0, cold.prediction.taken, phase='wrap-destination-cold-control')
    await agent.train(BpuTraining(DESTINATION, POSITION, TARGET, cold.meta.resolve, branch_type=1))
    first = await revisit(agent, observation, origin.meta.redirect)
    check(checker, 2, mbtb_counter_for_position(first, POSITION), phase='wrap-first-main-btb')
    if stage == 's2':
        return origin, first
    # Allocate negative TAGE providers using the same proven training sequence,
    # but keep each prediction's genuine pre-branch history at pointer0.
    await agent.train_batch(BpuBatchTraining(DESTINATION, first.meta.resolve, (
        BpuBranchFeedback(POSITION, TARGET, 1, taken=0), None,
        BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=1, mispredict=1))))
    residents = await revisit(agent, observation, origin.meta.redirect)
    check(checker, (1, 2), tuple(mbtb_counter_for_position(residents, position)
        for position in (POSITION, LATER_POSITION)), phase='wrap-residents')
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(DESTINATION, residents.meta.resolve,
        (BpuBranchFeedback(POSITION, TARGET, 1, taken=1, mispredict=1),)))
    single = await revisit(agent, observation, origin.meta.redirect)
    check(checker, 4, tage_meta_for_position(single, POSITION)['providerTakenCtr_value'], phase='wrap-provider4')
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(DESTINATION, single.meta.resolve,
        (BpuBranchFeedback(POSITION, TARGET, 1, taken=0, mispredict=1),)))
    negative = await revisit(agent, observation, origin.meta.redirect)
    check(checker, 3, tage_meta_for_position(negative, POSITION)['providerTakenCtr_value'], phase='wrap-provider3')
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(DESTINATION, negative.meta.resolve, (
        BpuBranchFeedback(POSITION, TARGET, 1, taken=0), None,
        BpuBranchFeedback(LATER_POSITION, LATER_TARGET, 1, taken=0, mispredict=1))))
    both = await revisit(agent, observation, origin.meta.redirect)
    check(checker, (2, 3), tuple(tage_meta_for_position(both, position)['providerTakenCtr_value']
        for position in (POSITION, LATER_POSITION)), phase='wrap-two-negative-providers')
    await agent.configure_predictors(sc=True, settle=True)
    qualified = await revisit(agent, observation, origin.meta.redirect)
    before = sc_meta_for_position(qualified, POSITION)
    check(checker, 2, before['tageCtr'], phase='wrap-sc-negative-provider')
    await agent.configure_predictors(tage=False, settle=True)
    await agent.train_batch_with_prediction_pause(BpuBatchTraining(DESTINATION, qualified.meta.resolve,
        (BpuBranchFeedback(POSITION, TARGET, 1, taken=1),)), repetitions=32)
    await agent.configure_predictors(tage=True, settle=True)
    return origin, qualified


async def check_taken_wrap(agent, output, *, stage, mode='flowing'):
    if stage not in ('s2', 's3') or mode not in ('flowing', 'backpressured'):
        raise ValueError('unknown wrap stage/cadence')
    checker = BpuPhrChecker(scope=dict(stage=stage, mode=mode, scenario='taken-pointer-zero-wrap'))
    observation = agent.observe_phr(checker)
    coverage = coverage_model(stage, mode)
    failure, witnesses, preparation = None, [], {}
    try:
        async with observation:
            origin, trained = await prepare(agent, observation, checker, stage)
            preparation.update(origin=asdict(origin), trained=asdict(trained))
            window = len(checker.records)
            preparation['wrap_window_start_tick'] = checker.records[-1]['tick']
            restored = await revisit(agent, observation, origin.meta.redirect, mode=mode, arm=True)
            preparation['restored'] = asdict(restored)
            await agent.set_ready(prediction=False, meta=True)
            await observation.drain()
            for index in range(window, len(checker.records) - 1):
                row = checker.records[index]
                request = row['boundary'][stage]
                if request['valid'] and request['start_pc'] == DESTINATION and request['prediction']['taken']:
                    next_row = checker.records[index + 1]
                    check(checker, dict(flag=0, value=0), request['meta']['pointer'],
                        phase='required-real-taken-wrap-input', stage=stage, tick=row['tick'])
                    check(checker, dict(flag=1, value=50), next_row['state']['pointer'],
                        phase='taken-wrap-result', stage=stage, tick=row['tick'])
                    check(checker, subtract(request['meta']['pointer'], 2), next_row['state']['pointer'],
                        phase='taken-wrap-independent-circular-arithmetic', stage=stage, tick=row['tick'])
                    check(checker, dict(start_pc=DESTINATION, target=TARGET, taken=1, position=POSITION,
                        s2_override=int(stage == 's2'), s3_override=int(stage == 's3')),
                        row['public_prediction']['bits'], phase='taken-wrap-public-correction', stage=stage)
                    check(checker, int(mode == 'flowing'), row['public_prediction']['ready'],
                        phase='taken-wrap-required-backpressure', stage=stage, mode=mode)
                    witnesses.append(dict(tick=row['tick'], request=deepcopy(request),
                        next_state=deepcopy(next_row['state']), output=deepcopy(row['public_prediction'])))
            check(checker, True, bool(witnesses), phase='required-valid-taken-pointer-zero-override', stage=stage)
            if stage == 's3':
                sc = sc_meta_for_position(restored, POSITION)
                check(checker, dict(tagePredValid=1, tageCtr=2, scPred=1, useScPred=1, sumAboveThres=1),
                    sc, phase='wrap-late-taken-sc-qualification')
            for phase in PHASES:
                coverage.sample(dict(checked=phase))
            coverage.assert_coverage(100.0)
            return checker.summary()
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        write_coverage(coverage, Path(output), stage, mode)
        dump_trace(Path(output, 'results/bpu', f'phr-wrap-{stage}-{mode}.json'), dict(stage=stage, mode=mode,
            failure=failure, trace=checker.records, witnesses=witnesses,
            preparation=preparation, accepted=observation.accepted,
            summary=None if failure else checker.summary(), formal_credit=False))
