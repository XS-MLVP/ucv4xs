"""Independent histories may retire in different logical orders on two owners."""
from bpuverify.bpu.checker.asymmetric_retirement import AsymmetricRetirementChecks
from bpuverify.bpu.env.asymmetric_retirement import prepare_asymmetric_retirement, AsymmetricRetirementService
from bpuverify.bpu.env.directions import direction_program
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS


async def check_asymmetric_retirement(agent, coverage):
    async with direction_program(agent, PC) as env:
        checks = AsymmetricRetirementChecks(env.checker, coverage)
        await prepare_asymmetric_retirement(env, checks)
        async with AsymmetricRetirementService(env, checks) as service:
            await service.start_stream()
            await service.submit_prelude()
            await service.submit_late_learning()
            for name, path in HISTORY_PATHS.items():
                checks.consume('blocked', name, await service.query(PC, via=path))
            await service.release()
            for name, path in HISTORY_PATHS.items():
                checks.consume('serviced', name, await env.capture_via(PC, path))
            checks.finish()
