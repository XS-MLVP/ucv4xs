"""Maintain semantic directions until real owned failures produce maintenance."""
from suites.frontend.bpu.bpu.case.early_positive import exercise_positive_opposition
from suites.frontend.bpu.bpu.checker.early_aging import EarlyAgingChecks
from suites.frontend.bpu.bpu.env.early_aging import early_aging_program
from suites.frontend.bpu.bpu.model.early_opposition import PC


async def check_early_aging(agent, coverage):
    checks = EarlyAgingChecks(coverage, PC)
    async with early_aging_program(agent, checks) as env:
        source = await exercise_positive_opposition(env, checks)
        checks.seed_history(checks.strong, False)
        source = await env.stable_positive(source)
        checks.seed_history(source, True)
        source = await env.highest_provider_error(source, checks)
        # A reset-derived pure program establishes this safety bound. Stop on
        # independently qualified maintenance, not elapsed cycles or sends.
        for _ in range(44):
            source = await env.steer_learning(source, 3, checks)
            if checks.ledger.ages:
                break
            source = await env.steer_learning(source, 0, checks)
        else:
            raise AssertionError(f'normal source program did not age: failures={checks.ledger.failures}, '
                                 f'count={checks.ledger.count}')
        source = await env.original_positive_after_aging(source, checks)
        checks.consumed(source, True)
        source = await env.negative_consumer_after_aging(source, checks)
        checks.consumed(source, False)
        checks.finish_aging(env.owners)
