"""Read and relearn mixed committed/pending branch versions through real sources."""
from suites.frontend.bpu.bpu.checker.mixed_visibility import MixedVisibilityChecks
from suites.frontend.bpu.bpu.env.directions import direction_program
from suites.frontend.bpu.bpu.env.mixed_visibility import prepare_mixed_visibility, MixedVisibilityService
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS


async def check_mixed_visibility(agent, program, coverage, *, checks_factory=MixedVisibilityChecks,
                                prepare=prepare_mixed_visibility,service_factory=MixedVisibilityService,evidence=None):
    async with direction_program(agent, PC) as env:
        checks = checks_factory(env.checker, coverage, program)
        try:
            await prepare(env, checks)
            async with service_factory(env, checks) as service:
                await service.start_stream()
                await service.submit_prelude()
                for name, path in HISTORY_PATHS.items():
                    checks.consume('initial', name, await service.query(PC, via=path))
                await service.release_one_pair()
                for name, path in HISTORY_PATHS.items():
                    checks.consume('mixed', name, await service.query(PC, via=path))
                await service.submit_mixed_learning()
                for name, path in HISTORY_PATHS.items():
                    checks.consume('blocked', name, await service.query(PC, via=path))
                await service.release()
                for name, path in HISTORY_PATHS.items():
                    checks.consume('serviced', name, await env.capture_via(PC, path))
                checks.finish()
        except BaseException as error:
            if evidence is not None:
                try:evidence.update(checks.snapshot())
                except Exception as snapshot_error:
                    evidence['snapshot_error']=repr(snapshot_error)
                    error.add_note('Secondary semantic snapshot error: '+repr(snapshot_error))
            raise
        else:
            if evidence is not None:evidence.update(checks.snapshot())
