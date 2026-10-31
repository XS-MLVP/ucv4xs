"""Genuine metadata recovery sequences; test functions only choose domain intent."""

from suites.frontend.bpu.runtime.trace import dump_trace
from copy import deepcopy
from pathlib import Path
from toffee import CheckContext
from toffee import ScoreboardMode

from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.model.phr.model import subtract
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from suites.frontend.bpu.bpu.coverage.phr.supplemental import bpu_phr_recovery_coverage_model as coverage_model
from suites.frontend.bpu.bpu.coverage.phr.supplemental import write_bpu_phr_recovery_coverage as write_coverage

PC = 0x40000800


async def check_recovery(agent, output, *, mode, steps=52):
    if mode not in ('flowing', 'backpressured'):
        raise ValueError('unknown recovery cadence')
    checker = BpuPhrChecker(scope=dict(mode=mode, steps=steps))
    observation = agent.observe_phr(checker)
    coverage = coverage_model(mode)
    observations, routes = [], set()
    failure = None
    try:
        async with observation:
            await agent.reset(PC)
            # Let all SRAM initialization and the first enabled lookup finish.
            # Disabling before that freezes uninitialized predictor read state.
            current = await agent.next_transaction( start_pc=PC)
            checker.scoreboard.check(expected=0, actual=current.prediction.taken,
                context=CheckContext(scoreboard=checker.scoreboard.name, mode=ScoreboardMode.DIRECT,
                    request=dict(mode=mode, phase='qualified-cold-start', start_pc=PC)))
            await agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
                tage=False, sc=False, ittage=False, ras=False, settle=True)
            for step in range(steps):
                for taken in (0, 1):
                    anchor = deepcopy(current.meta.redirect)
                    previous = anchor['phr']
                    target = PC + 0x100 * (1 + 2 * step + taken)
                    cfi_pc = current.prediction.start_pc + 1 + step % 7
                    request = BpuRedirect(target, anchor, cfi_pc=cfi_pc, taken=taken, branch_type=1)
                    if mode == 'backpressured':
                        await agent.set_ready(prediction=False, meta=True)
                        await observation.drain()
                    await agent.redirect(request)
                    if mode == 'backpressured':
                        await observation.drain()
                        await agent.set_ready(prediction=True, meta=True)
                    current = await agent.next_transaction( start_pc=target)
                    checker.raise_failure()
                    wanted = dict(phrPtr=subtract(previous['phrPtr'], 2 * taken),
                        phrLowBits=(((previous['phrLowBits'] << 2) ^ path_hash(cfi_pc, target)) & 8191)
                            if taken else previous['phrLowBits'])
                    actual = current.meta.redirect['phr']
                    context = CheckContext(scoreboard=checker.scoreboard.name, mode=ScoreboardMode.DIRECT,
                        sequence_id=len(observations), request=dict(mode=mode, step=step,
                            taken=taken, cfi_pc=cfi_pc, target=target, meta=anchor))
                    checker.scoreboard.check(expected=wanted, actual=actual, context=context)
                    coverage.sample(dict(flag=previous['phrPtr']['flag'], pointer=previous['phrPtr']['value'], taken=taken))
                    routes.add((mode, previous['phrPtr']['flag'], previous['phrPtr']['value'], taken))
                    observations.append(dict(step=step, taken=taken, request=dict(cfi_pc=cfi_pc,
                        target=target, meta=anchor), expected_next=wanted, actual_next=deepcopy(actual)))
            await agent.set_ready(prediction=False, meta=True)
            await observation.drain()
            summary = checker.summary()
            if steps == 52:
                required = {(mode, flag, value, taken) for flag in (0, 1) for value in range(0, 52, 2) for taken in (0, 1)}
                checker.scoreboard.check(expected=sorted(required), actual=sorted(routes), context=context)
            return summary
    except BaseException as error:
        failure = repr(error)
        raise
    finally:
        write_coverage(coverage, Path(output), mode)
        path = Path(output) / 'results/bpu' / ('phr-recovery-' + mode + '.json')
        dump_trace(path, dict(mode=mode, steps=steps, trace=checker.records,
            observations=observations, accepted=observation.accepted, routes=sorted(routes),
            failure=failure, summary=None if failure else checker.summary(), formal_credit=False))
