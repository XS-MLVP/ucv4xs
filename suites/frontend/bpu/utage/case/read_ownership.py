"""A query owns its old logical record even when B learning reuses storage."""
from suites.frontend.bpu.utage.checker.read_ownership import ReadOwnershipChecks
from suites.frontend.bpu.utage.env.read_ownership import ReadOwnershipEnv
from suites.frontend.bpu.utage.monitor.read_ownership import ReadOwnershipMonitor


async def check_read_ownership(agent, program, coverage):
    await agent.reset()
    checks = ReadOwnershipChecks(program, coverage)
    env = ReadOwnershipEnv(agent, program, checks)
    async with ReadOwnershipMonitor(agent, checks) as monitor:
        try:
            await env.prepare()
            actuals = await env.overlap()
            checks.feedback_once(env.ledger, env.expected_feedback)
            checks.actual_reuse(tuple(monitor.records), env.transfers)
            checks.responses(env.transfers, actuals)
            await env.consumers()
            agent.reference.raise_failure()
            checks.finish(env.originals)
        except Exception as error:
            # Preserve the earliest independent checker exception. Qualify
            # actual reach even if it stopped before the normal case drain.
            if env.transfers:
                try:
                    checks.feedback_once(env.ledger, env.expected_feedback)
                    witness = checks.actual_reuse(tuple(monitor.records), env.transfers)
                    error.add_note('Actual in-flight ownership window: '+repr(witness))
                except Exception as qualification:
                    error.add_note('In-flight window not qualified: '+str(qualification))
                error.add_note('Bounded actual context: '+repr(monitor.diagnostic()))
            raise
