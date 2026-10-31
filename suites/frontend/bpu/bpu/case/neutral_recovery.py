"""Contribution, direction learning and protection limits in a real BPU path."""
from suites.frontend.bpu.bpu.model.early_opposition import PC
from suites.frontend.bpu.bpu.model.early_positive_protection import OLDER_PATHS
from suites.frontend.bpu.bpu.checker.neutral_recovery import Checks
from suites.frontend.bpu.bpu.env.neutral_recovery import program


async def run(agent, profile, coverage, evidence):
    checks = Checks(coverage, profile, PC)
    try:
        async with program(agent, checks) as env:
            source = await env.prepare()
            if profile == 'neutral-lower':
                source = await env.steer_main(source, 0)
                source = await env.edge(source, 'T-error-to-zero', taken=True, older=OLDER_PATHS[0])
                source = await env.base_bias(source, taken=False)
                source = await env.edge(source, 'neutral-at-zero', taken=False, older=OLDER_PATHS[0])
                source = await env.steer_main(source, 3)
                source = await env.edge(source, 'first-NT-error', taken=False)
                source = await env.edge(source, 'NT-error-restores-T', taken=False)
                source = await env.base_bias(source, taken=False)
                source = await env.steer_main(source, 3)
                source = await env.edge(source, 'contribution-restores-protection', taken=True)
            else:
                for _ in range(3): source = await env.original_taken(source)
                for name in ('approach-upper', 'reach-upper'):
                    source = await env.base_bias(source, taken=False)
                    source = await env.steer_main(source, 3)
                    source = await env.edge(source, name, taken=True)
                source = await env.base_bias(source, taken=True)
                source = await env.edge(source, 'neutral-at-upper', taken=True)
                source = await env.steer_main(source, 0)
                source = await env.edge(source, 'error-releases-upper', taken=True, older=OLDER_PATHS[1])
            await env.consume_final(source)
            checks.finish_boundaries(env.owners)
    finally: evidence.update(checks.snapshot())
