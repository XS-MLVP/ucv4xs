"""Real original lifetimes through existing asynchronous drivers and monitors."""
from copy import deepcopy
from hashlib import sha256
import json
from bpuverify.utage.transaction.types import UtageBaseBranch, UtageTraining
from bpuverify.utage.model.displaced_branch import PC, EARLY
from bpuverify.utage.checker.displaced_branch import Checks
from bpuverify.utage.monitor.dual_source import Monitor


async def run(agent, program, coverage, evidence):
    await agent.reset()
    checks = Checks(program)
    monitor = Monitor(agent).start()
    accepted = agent.reference.model.accepted_feedback
    primary = None
    fingerprint = lambda x:sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()

    def submit(positions):
        return agent.submit_predict_branches(PC,tuple(None if p is None else
            UtageBaseBranch(p,int(p == EARLY)) for p in positions))

    async def obtain(label, positions, state):
        handle = submit(positions)
        source = await handle
        return checks.query(label,positions,state,handle,source,monitor),source

    async def originals(state):
        positions = program.positions()
        if program.mode == 'adjacent':
            handles = [submit(positions) for _ in range(2)]
            await agent.drain_predictions()
            result = []
            for i,handle in enumerate(handles):
                source = await handle
                result.append((checks.query('held-original-'+str(i),positions,state,handle,source,monitor),source))
            return result
        return [await obtain('held-original-'+str(i),positions,state) for i in range(2)]

    def training(step, original):
        token,source = original
        tx = UtageTraining(PC,step.position,step.taken,deepcopy(source.meta),
            mispredict=int(step.error),branch_type=step.kind)
        checks.owned_feedback(step,token,tx)
        return tx

    async def consume(label, step):
        handle = submit(program.positions(consumer=True))
        checks.consume(label,step,handle,await handle,monitor)

    try:
        checks.check(program.protection_after(0),monitor.all_protection(),'normal reset is the only initial state')
        cold = await obtain('held-cold-installation',program.positions(program.replacement_position),(None,None))
        held = None
        for step in program.steps[:program.preparation_count]:
            if step.ordinal == program.capture_after:
                held = await originals(step.before)
            original = cold if step.ordinal == program.preparation_count-1 else await obtain(
                step.name,program.positions(step.seed_position),step.sources)
            await agent.train(training(step,original))
            checks.prefix(monitor,step.ordinal+1)
            await consume('after-'+step.name,step)
        if held is None: raise AssertionError('two declared old original occurrences must be captured')
        for rule in program.rules[:4]: coverage.reach(rule)
        late = program.steps[-2:]
        if program.mode == 'adjacent':
            transactions = tuple(training(step,original) for step,original in zip(late,held,strict=True))
            await agent.train_many(transactions)
            checks.prefix(monitor,len(program.steps))
        else:
            for step,original in zip(late,held,strict=True):
                await agent.train(training(step,original))
                checks.prefix(monitor,step.ordinal+1)
                await consume('after-'+step.name,step)
        await consume('final-three-instructions',late[-1])
        checks.check(len(program.steps),agent.reference.model.accepted_feedback-accepted,'every declared original teaches once')
        checks.check((program.failed_allocations,)*2,(agent.reference.model.low_tick,agent.reference.model.high_tick),
            'only original errors consume the declared protected allocation failures; no maintenance')
        delta = checks.finish(monitor)
        agent.reference.raise_failure()
        for rule in program.rules[4:]: coverage.reach(rule,compared=checks.compared)
        evidence.update(checks.snapshot(),status='COMPARED',closed=False,
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates,
            actual_feedbacks=[dict(tick=r['tick'],payload_sha256=fingerprint(r['bits'])) for r in monitor.public],
            expected_feedback_sha256=[fingerprint(v) for v in checks.expected_feedback],
            late_feedback_tick_delta=delta,all_protection_cells_compared=1024,
            reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        primary = error
        evidence.update(checks.snapshot(),status='FAIL',closed=False,error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual))
                for d in getattr(error,'differences',())[:12]],
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates)
        raise
    finally:
        try: await monitor.aclose()
        except BaseException as error:
            evidence.update(status='FAIL',closed=False,cleanup_error=repr(error))
            if primary is None: raise
            primary.add_note(f'displaced-branch monitor cleanup: {error!r}')
    coverage.finish()
    evidence.update(status='PASS',closed=True,completed=list(program.rules))
