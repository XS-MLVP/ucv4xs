"""Semantic query identity and recovery source intent, outside pytest bodies."""
from copy import deepcopy

from suites.frontend.bpu.utage.checker.source_ownership import SourceOwnershipChecks
from suites.frontend.bpu.utage.driver.recovery import RecoveryDriver
from suites.frontend.bpu.utage.env.source_ownership import SourceOwnershipEnv
from suites.frontend.bpu.utage.monitor.source_ownership import SourceOwnershipMonitor
from suites.frontend.bpu.utage.model.source_ownership import POSITION
from suites.frontend.bpu.utage.transaction.types import UtageTraining


async def check_request_ownership(agent, program, coverage):
    checks = SourceOwnershipChecks(program, coverage); env = SourceOwnershipEnv(agent, checks)
    await env.prepare(program.profiles)
    checks.begin('prepared-identities'); checks.end('prepared-identities')
    transfers, actuals = await env.burst(program.sequence)
    checks.overlapping(transfers)
    checks.begin('complete-responses')
    for (profile, base), actual in zip(program.sequence, actuals, strict=True): checks.profile(profile, actual, base)
    checks.end('complete-responses')
    await env.consumers(program.profiles[:3], 'preserved-neighbors')
    checks.immutable(env.originals)


async def check_saved_source(agent, program, coverage):
    checks = SourceOwnershipChecks(program, coverage); env = SourceOwnershipEnv(agent, checks)
    sources = await env.prepare(program.profiles)
    # Prime the current read with the distinct decoy, not a source that could
    # be mistaken for the first input of the compound protocol.
    await env.read(program.decoy)
    feedback = UtageTraining(program.target.pc, POSITION, program.target.taken,
        deepcopy(sources[program.target.name].meta), mispredict=0) if program.learning else None
    async with SourceOwnershipMonitor(agent) as monitor:
        accepted = await RecoveryDriver(agent).send(program, feedback)
        rows = monitor.recovery_rows(program)
        checks.lineage(rows, accepted)
        public = tuple(row.shadow['public']['bits'] for row in monitor.records if row.shadow['public']['valid'])
        checks.check(() if feedback is None else (agent.encode_training(feedback),), public,
                     'complete original feedback accepted once, no forged snapshot')
        checks.recovery(rows[-1])
    final = tuple(program.latest if p.name == program.target.name else p for p in program.profiles)
    await env.consumers(final, 'fresh-consumers')
    checks.immutable(env.originals)
