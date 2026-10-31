"""Concurrent real original feedback, with timing owned by public drivers."""
from copy import deepcopy
from hashlib import sha256
import json
from suites.frontend.bpu.utage.transaction.types import UtageBaseBranch,UtageTraining
from suites.frontend.bpu.utage.model.instruction_confidence import PC
from suites.frontend.bpu.utage.checker.instruction_confidence import Checks
from suites.frontend.bpu.utage.monitor.dual_source import Monitor


async def run(agent,program,coverage,evidence):
    await agent.reset()
    checks=Checks(program);monitor=Monitor(agent).start()
    accepted=agent.reference.model.accepted_feedback;primary=None
    fingerprint=lambda value:sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    def submit(positions):
        return agent.submit_predict_branches(PC,tuple(None if p is None else
            UtageBaseBranch(p,int(p in (2,7))) for p in positions))
    async def obtain(label,positions,state):
        handle=submit(positions);source=await handle
        return checks.query(label,positions,state,handle,source,monitor),source
    async def originals(state):
        positions=program.positions()
        handles=[submit(positions) for _ in range(2)]
        await agent.drain_predictions()
        result=[]
        for number,handle in enumerate(handles):
            source=await handle
            result.append((checks.query('held-original-'+str(number),positions,state,handle,source,monitor),source))
        return result
    def training(step,original):
        token,source=original
        tx=UtageTraining(PC,step.position,step.taken,deepcopy(source.meta),mispredict=int(step.error),branch_type=step.kind)
        checks.owned_feedback(step,token,tx)
        return tx
    async def consume(label,step):
        handle=submit(program.positions(consumer=True))
        checks.consume(label,step,handle,await handle,monitor)
    try:
        checks.check(program.protection_after(0),monitor.all_protection(),'normal reset supplies all initial state')
        cold=await obtain('held-cold-installation',program.positions(program.replacement_position),(None,None))
        held=None
        for step in program.steps[:8]:
            original=await obtain(step.name,program.positions(step.seed_position),step.sources)
            await agent.train(training(step,original));checks.prefix(monitor,step.ordinal+1)
            await consume('after-'+step.name,step)
            if step.ordinal+1==program.capture_after:held=await originals(step.after)
        if held is None:raise AssertionError('two distinct old occurrences must precede installation')
        for rule in program.rules[:4]:coverage.reach(rule)
        install=program.steps[8];late=program.steps[-2:]
        if program.mode=='adjacent':
            transactions=[training(install,cold)]
            transactions.extend(training(step,original) for step,original in zip(late,held,strict=True))
            await agent.train_many(tuple(transactions))
            checks.prefix(monitor,len(program.steps))
        else:
            await agent.train(training(install,cold));checks.prefix(monitor,9)
            await consume('after-installation',install)
            for step,original in zip(late,held,strict=True):
                await agent.train(training(step,original));checks.prefix(monitor,step.ordinal+1)
                await consume('after-'+step.name,step)
        await consume('final-complete-vector',late[-1])
        checks.check(len(program.steps),agent.reference.model.accepted_feedback-accepted,'all declared original occurrences teach once')
        checks.check((program.failed_allocations,)*2,(agent.reference.model.low_tick,agent.reference.model.high_tick),
            'normal protected allocation failures only, without hidden maintenance')
        cadence=checks.finish(monitor);agent.reference.raise_failure()
        for rule in program.rules[4:]:coverage.reach(rule)
        evidence.update(checks.snapshot(),status='COMPARED',closed=False,cadence=cadence,
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates,
            actual_feedbacks=[dict(tick=r['tick'],payload_sha256=fingerprint(r['bits'])) for r in monitor.public],
            expected_feedback_sha256=[fingerprint(v) for v in checks.expected_feedback],all_protection_cells_compared=1024)
    except BaseException as error:
        primary=error
        evidence.update(checks.snapshot(),status='FAIL',closed=False,error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]],
            actual_learning=monitor.records,actual_native_writes=monitor.native_updates,
            actual_feedbacks=[dict(tick=r['tick'],payload_sha256=fingerprint(r['bits'])) for r in monitor.public])
        raise
    finally:
        try:await monitor.aclose()
        except BaseException as error:
            evidence.update(status='FAIL',closed=False,cleanup_error=repr(error))
            if primary is None:raise
            primary.add_note(f'instruction-confidence monitor cleanup: {error!r}')
    coverage.finish();evidence.update(status='PASS',closed=True,completed=list(program.rules))
