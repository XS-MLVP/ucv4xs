"""Actual recovery outcomes in each address/history class; no public-target credit."""
from copy import deepcopy

from suites.frontend.bpu.testbenches.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.testbenches.bpu.coverage.redirect_matrix import RedirectMatrixCoverage
from suites.frontend.bpu.testbenches.bpu.env.agent.pipeline import PipelineObservation
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT


async def check_redirect_matrix(agent, case):
    coverage = RedirectMatrixCoverage(case)
    phr = BpuPhrChecker(scope='guard/sign/outcome with original history', record_limit=8)
    try:
        async with PipelineObservation(agent) as observation, agent.observe_phr(phr) as history:
            await agent.reset(case.boot_pc)
            source = await agent.next_transaction(start_pc=case.boot_pc)
            await agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
                tage=False, sc=False, ittage=False, ras=False, settle=True)
            # Bootstrap by actual redirect. Its independently chosen low bits
            # have zero path contribution, preserving the empty-history class.
            bootstrap = BpuRedirect(case.pc, source.meta.redirect, cfi_pc=case.boot_pc + 4)
            assert ((16 * ((case.boot_pc + 4) % 512)) ^ ((case.pc // 2) % 32768)) == 0
            observation.checker.plan_redirect(source, bootstrap)
            accepted = await agent.redirect(bootstrap)
            source = await agent.next_transaction(start_pc=case.pc, after_tick=accepted)
            if case.history == 'nonzero':
                # Two actual taken recoveries, not model state seeding. Return
                # to the same PC with a fresh UID and a nonzero owned prefix.
                for target in (case.pc + 0x120, case.pc):
                    request = BpuRedirect(target, source.meta.redirect,
                                          cfi_pc=source.prediction.start_pc + 3)
                    observation.checker.plan_redirect(source, request)
                    accepted = await agent.redirect(request)
                    source = await agent.next_transaction(start_pc=target, after_tick=accepted)
            token = observation.checker.source_token(source)
            original = token.history.history
            assert bool(original) == (case.history == 'nonzero')
            frozen = deepcopy(source.meta.redirect)
            request = BpuRedirect(case.target, source.meta.redirect,
                cfi_pc=case.cfi, taken=case.taken, branch_type=1)
            observation.checker.plan_redirect(source, request)
            async with agent.observe_guarded_redirect() as frames:
                accepted = await agent.redirect(request)
                coverage.record('reached', tick=accepted, owner=token.sequence, history=original)
                consumer = await agent.next_transaction(start_pc=case.target, after_tick=accepted)
            assert frames == [case.boundary]
            new = observation.checker.source_token(consumer)
            assert new.history.history == case.next_history(original)
            assert new.sequence != token.sequence
            assert source.meta.redirect == frozen
            await agent.set_ready(prediction=False, meta=True)
            await history.drain()
            observation.checker.raise_failure()
            assert phr.summary()['accepted'] == (4 if case.history == 'nonzero' else 2)
        coverage.record('checked', owner=new.sequence, history=new.history.history)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
