"""Domain vector lifecycle; drivers own all timing and monitor native writes."""
from copy import deepcopy
from hashlib import sha256
import json
from suites.frontend.bpu.utage.transaction.types import UtageBaseBranch, UtageTraining
from suites.frontend.bpu.utage.model.dual_source import PC, EARLY
from suites.frontend.bpu.utage.checker.dual_source import Checks
from suites.frontend.bpu.utage.monitor.dual_source import Monitor


async def run(agent, program, coverage, evidence):
    await agent.reset()
    checks = Checks(program)
    monitor = Monitor(agent).start()
    accepted = agent.reference.model.accepted_feedback
    primary = None
    fingerprint = lambda value:sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def submit(seed_position=None):
        positions = program.positions(seed_position)
        branches = tuple(None if p is None else UtageBaseBranch(p,int(p==EARLY)) for p in positions)
        return agent.submit_predict_branches(PC,branches)
    async def obtain(step):
        handle = submit(step.seed_position)
        source = await handle
        token = checks.query(step.name,program.positions(step.seed_position),step.sources,handle,source,monitor)
        return token,source
    def training(step, original):
        token,source = original
        tx = UtageTraining(PC,step.position,step.taken,deepcopy(source.meta),
            mispredict=int(step.error),branch_type=step.kind)
        checks.owned_feedback(step,token,tx)
        return tx
    async def consume(label, step):
        handle = submit()
        source = await handle
        checks.consume(label,step,handle,source,monitor)

    try:
        checks.check(program.protection_after(0),monitor.all_protection(),'normal reset supplies the only initial state')
        for step in program.steps[:program.preparation_count]:
            original = await obtain(step)
            await agent.train(training(step,original))
            checks.prefix(monitor,step.ordinal+1)
            await consume('after-'+step.name,step)
        late = program.steps[program.preparation_count:]
        originals = []
        if program.mode=='adjacent':
            handles = [submit() for _ in late]
            await agent.drain_predictions()
            for step,handle in zip(late,handles,strict=True):
                source = await handle
                originals.append((checks.query(step.name,program.positions(),step.sources,handle,source,monitor),source))
        else:
            for step in late:originals.append(await obtain(step))
        for rule in program.rules[:3]:coverage.reach(rule)
        if program.mode=='adjacent':
            transactions = tuple(training(step,original) for step,original in zip(late,originals,strict=True))
            await agent.train_many(transactions)
            await consume('final-full-vector',late[-1])
            checks.prefix(monitor,len(program.steps))
        else:
            for step,original in zip(late,originals,strict=True):
                await agent.train(training(step,original))
                await consume('after-'+step.name,step)
                checks.prefix(monitor,step.ordinal+1)
            await consume('final-full-vector',late[-1])
        checks.check(len(program.steps),agent.reference.model.accepted_feedback-accepted,'all declared distinct original vectors teach exactly once')
        checks.check((program.failed_allocations,)*2,(agent.reference.model.low_tick,agent.reference.model.high_tick),
            'only declared protected/no-deeper allocation failures; no hidden maintenance')
        delta = checks.finish(monitor)
        agent.reference.raise_failure()
        for rule in program.rules[3:]:coverage.reach(rule,compared=checks.compared)
        coverage.finish()
        evidence.update(checks.snapshot(),status='PASS',closed=True,completed=list(program.rules),
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates,
            actual_feedbacks=[dict(tick=r['tick'],payload_sha256=fingerprint(r['bits'])) for r in monitor.public],
            expected_feedback_sha256=[fingerprint(v) for v in checks.expected_feedback],
            late_feedback_tick_delta=delta,all_protection_cells_compared=1024,
            reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        primary = error
        evidence.update(checks.snapshot(),status='FAIL',error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]],
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates,
            actual_feedbacks=[dict(tick=r['tick'],payload_sha256=fingerprint(r['bits'])) for r in monitor.public],
            expected_feedback_sha256=[fingerprint(v) for v in checks.expected_feedback])
        raise
    finally:
        try:await monitor.aclose()
        except BaseException as error:
            if primary is None:raise
            primary.add_note(f'dual-source monitor cleanup: {error!r}')
