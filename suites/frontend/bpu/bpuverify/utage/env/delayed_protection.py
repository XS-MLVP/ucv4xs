"""Actual original transfers, delayed feedback, complete learning witnesses."""
from copy import deepcopy
from hashlib import sha256
import json
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.model.delayed_protection import PC, POSITION, READ_PCS, RULES
from bpuverify.utage.checker.delayed_protection import Checks
from bpuverify.utage.monitor.selective_protection import Monitor


async def run(agent, p, coverage, evidence):
    await agent.reset()
    checks = Checks(p); monitor = Monitor(agent).start(); sources = {}; primary = None
    before = agent.reference.model.accepted_feedback
    rules = getattr(p, 'rules', RULES)
    expected_feedback = len(p.steps)

    async def queries(specs):
        handles = []; actuals = []
        for owner, history, base in specs:
            handle = agent.submit_predict(PC, POSITION, base, folded_history=history,
                index_pc=READ_PCS[owner], index_history=0)
            handles.append(handle)
            if p.mode == 'serial': actuals.append(await handle)
        if p.mode == 'adjacent':
            await agent.drain_predictions()
            actuals = [await handle for handle in handles]
        return tuple(zip(handles, actuals, strict=True))

    async def obtain(steps):
        pairs = await queries(tuple((step.owner, step.history, step.base) for step in steps))
        for step, (handle, source) in zip(steps, pairs, strict=True):
            ordinal = checks.owned_source(step, handle, source, monitor)
            sources[step.phase, step.owner] = source, ordinal
        return pairs

    async def consumers(phase, owners):
        history = 0 if phase == 'final-long' else 64
        pairs = await queries(tuple((owner, history, owner) for owner in owners))
        for owner, (handle, source) in zip(owners, pairs, strict=True): checks.consume(phase, owner, handle, source, monitor)

    try:
        checks.check(p.protection_after(0), monitor.all_protection(), 'normal reset before every genuine original')
        for group in p.groups:
            phase = group[0].phase
            if phase == 'allocate': await obtain(group)
            if phase == 'flip' and not any(key[0] == 'flip' for key in sources):
                # Both old predictions exist before either identity changes.
                for role in getattr(p, 'initial_roles', ('late-correct', 'flip')):
                    await obtain(tuple(p.step(role, owner) for owner in (0, 1)))
                coverage.reach(rules[0], original_sources=checks.snapshot()['originals'])
            transactions = []
            for step in group:
                source, ordinal = sources[step.phase, step.owner]
                if phase.startswith('late'):
                    previous = next(row['versions']['0'] for row in reversed(monitor.records)
                        if row['versions'].get('0', {}).get('new_cell', {}).get('index') == step.indices[0])
                    native = monitor.shadows[0].sample_at(agent.reference.last_event).value
                    checks.before_late(step, native['cells'][previous['sequence'] % len(native['cells'])], previous,
                        agent.reference.last_event.tick, monitor.all_protection())
                predicted = step.base if step.before is None else step.before.taken
                transaction = UtageTraining(PC, POSITION, step.actual, deepcopy(source.meta), mispredict=int(predicted != step.actual))
                checks.owned_feedback(step, ordinal, transaction); transactions.append(transaction)
            public_before = len(monitor.public)
            if p.mode == 'adjacent':
                await agent.train_many(tuple(transactions))
                checks.prefix(monitor, group[-1].ordinal+1)
            else:
                for step, transaction in zip(group, transactions, strict=True):
                    await agent.train(transaction); checks.prefix(monitor, step.ordinal+1)
            checks.cadence(group, monitor.public[public_before:])
            owners = tuple(step.owner for step in group)
            if phase == 'flip':
                for role in getattr(p, 'after_flip_roles', ('late-wrong',)):
                    pairs = await obtain(tuple(p.step(role, owner) for owner in owners))
                    if role == 'late-wrong':
                        for owner, (handle, source) in zip(owners, pairs, strict=True):
                            checks.consume('flip', owner, handle, source, monitor, existing_source=True)
            elif phase.startswith('late'): await consumers(phase, owners)
        for phase in ('final-short', 'final-long'): await consumers(phase, (0, 1))
        checks.check((2, 2), (agent.reference.model.low_tick, agent.reference.model.high_tick),
            'only the two declared companion-allocation failures; no hidden maintenance')
        checks.check(expected_feedback, agent.reference.model.accepted_feedback-before, 'all distinct complete original feedbacks accepted once')
        checks.finish(monitor); agent.reference.raise_failure()
        for rule in rules[1:]: coverage.reach(rule, delayed=checks.snapshot()['delayed'])
        coverage.finish()
        fingerprint = lambda value:sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        evidence.update(checks.snapshot(), status='PASS', actual_learning=monitor.records,
            public_feedbacks=[dict(tick=row['tick'], payload_sha256=fingerprint(row['bits'])) for row in monitor.public],
            expected_feedback_sha256=[fingerprint(value) for value in checks.expected_feedback],
            accepted_feedbacks=agent.reference.model.accepted_feedback-before,
            protection_endpoint_sha256=fingerprint(monitor.all_protection()),
            expected_protection_endpoint_sha256=fingerprint(p.protection_after(expected_feedback)), all_protection_cells_compared=1024,
            reference_failures=agent.reference.board.status.failed)
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
            primary.add_note(f'delayed-protection monitor cleanup: {error!r}')
