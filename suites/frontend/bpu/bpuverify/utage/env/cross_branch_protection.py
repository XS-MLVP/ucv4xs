"""Four branch originals through existing public drivers and semantic monitors."""
from copy import deepcopy
from hashlib import sha256
import json
from bpuverify.utage.checker.cross_branch_protection import Checks
from bpuverify.utage.monitor.selective_protection import Monitor
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.model.cross_branch_protection import POSITION, RULES


async def run(agent, program, coverage, evidence):
    await agent.reset()
    checks = Checks(program)
    monitor = Monitor(agent).start()
    sources = {}
    primary = None
    before = agent.reference.model.accepted_feedback

    async def queries(specs):
        handles, actuals = [], []
        for owner, history, base in specs:
            handle = agent.submit_predict(program.pc(owner), POSITION, base, folded_history=history,
                index_pc=program.read_pc(owner), index_history=0)
            handles.append(handle)
            if program.mode == 'serial': actuals.append(await handle)
        if program.mode == 'adjacent':
            await agent.drain_predictions()
            actuals = [await handle for handle in handles]
        return tuple(zip(handles, actuals, strict=True))

    async def obtain(steps):
        pairs = await queries(tuple((s.owner, s.history, s.base) for s in steps))
        for step, (handle, source) in zip(steps, pairs, strict=True):
            sources[step.phase, step.owner] = source, checks.owned_source(step, handle, source, monitor)
        return pairs

    async def consume(phase, owners):
        history = 0 if phase == 'final-long' else 64
        pairs = await queries(tuple((o, history, program.taken(o)) for o in owners))
        for owner, (handle, source) in zip(owners, pairs, strict=True): checks.consume(phase, owner, handle, source, monitor)

    try:
        checks.check(program.protection_after(0), monitor.all_protection(), 'all protection is genuinely reset before learning')
        for group in program.groups:
            phase = group[0].phase
            if phase == 'allocate': await obtain(group)
            if phase == 'flip':
                for role in ('late-correct', 'flip'): await obtain(tuple(program.step(role, o) for o in program.owners))
                for rule in RULES[:3]: coverage.reach(rule, matching_pcs=program.state()['matching_pcs'])
            requests = []
            for step in group:
                source, ordinal = sources[step.phase, step.owner]
                if phase.startswith('late'):
                    latest = next(row['versions']['0'] for row in reversed(monitor.records)
                        if row['versions'].get('0', {}).get('new_cell', {}).get('index') == step.indices[0])
                    native = monitor.shadows[0].sample_at(agent.reference.last_event).value
                    current = native['cells'][latest['sequence'] % len(native['cells'])]
                    checks.before_late(step, current, latest, agent.reference.last_event.tick, monitor.all_protection())
                predicted = step.base if step.before is None else step.before.taken
                transaction = UtageTraining(step.pc, POSITION, step.actual, deepcopy(source.meta), mispredict=int(predicted != step.actual))
                checks.owned_feedback(step, ordinal, transaction)
                requests.append(transaction)
            public_before = len(monitor.public)
            if program.mode == 'adjacent':
                await agent.train_many(tuple(requests))
                checks.prefix(monitor, group[-1].ordinal+1)
            else:
                for step, transaction in zip(group, requests, strict=True):
                    await agent.train(transaction)
                    checks.prefix(monitor, step.ordinal+1)
            checks.cadence(group, monitor.public[public_before:])
            owners = tuple(s.owner for s in group)
            if phase == 'flip':
                pairs = await obtain(tuple(program.step('late-wrong', o) for o in owners))
                for owner, (handle, source) in zip(owners, pairs, strict=True): checks.consume(phase, owner, handle, source, monitor, existing_source=True)
            elif phase.startswith('late'): await consume(phase, owners)
        for phase in ('final-short', 'final-long'): await consume(phase, program.owners)
        checks.check((4, 4), (agent.reference.model.low_tick, agent.reference.model.high_tick), 'only the four declared failed companion allocations, without maintenance')
        checks.check(16, agent.reference.model.accepted_feedback-before, 'all16 distinct original feedbacks accepted once')
        checks.finish(monitor)
        agent.reference.raise_failure()
        for rule in RULES[3:]: coverage.reach(rule, compared=checks.compared)
        coverage.finish()
        fingerprint = lambda value: sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        evidence.update(checks.snapshot(), status='PASS', actual_learning=monitor.records,
            actual_feedbacks=[dict(tick=r['tick'], payload_sha256=fingerprint(r['bits'])) for r in monitor.public],
            expected_feedback_sha256=[fingerprint(value) for value in checks.expected_feedback],
            protection_endpoint_sha256=fingerprint(monitor.all_protection()),
            expected_protection_endpoint_sha256=fingerprint(program.protection_after(16)),
            all_protection_cells_compared=1024, reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        primary = error
        evidence.update(checks.snapshot(), status='FAIL', error_type=type(error).__name__, error=str(error)[:6000],
            first_differences=[dict(path=d.path, expected=repr(d.expected), actual=repr(d.actual)) for d in getattr(error, 'differences', ())[:12]],
            actual_learning=monitor.records, observed_public_feedbacks=len(monitor.public))
        raise
    finally:
        try: await monitor.aclose()
        except BaseException as error:
            if primary is None: raise
            primary.add_note(f'cross-branch protection monitor cleanup: {error!r}')
