"""Concurrent public drivers; version semantics and phase witnesses stay here."""
import asyncio
from contextlib import suppress
from copy import deepcopy

from toffee import AnyOf,SimTimeout,TaskComplete,XEventKind
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.read_lifetime import PC,POSITION,NEIGHBOR,RULES
from suites.frontend.bpu.utage.checker.read_lifetime import Checks,values
from suites.frontend.bpu.utage.monitor.read_lifetime import ReadLifetimeMonitor


class ReadLifetime:
    def __init__(self,agent,program,coverage,evidence):
        self.agent,self.program,self.coverage,self.evidence=agent,program,coverage,evidence
        self.checks=Checks(program)
        self.sources=[]

    async def source(self,pc,history,base,expected):
        source=await self.agent.predict(pc,POSITION,base,folded_history=history)
        self.checks.check(expected,values(source),'fresh complete source from normal public prediction')
        self.sources.append((source,deepcopy(source.meta)))
        return source

    async def teach(self,source,pc,actual):
        await self.agent.train(UtageTraining(pc,POSITION,actual,deepcopy(source.meta),
            mispredict=int(source.taken!=actual)))

    async def prepared(self):
        p=self.program
        await self.agent.reset()
        cold=await self.source(PC,0,0,(0,None,None,None))
        await self.teach(cold,PC,1)
        short=await self.source(PC,0,0,(1,0,4,1))
        if p.profile=='different-identity-replacement':
            await self.teach(short,PC,0)
            await self.source(PC,0,1,(1,1,3,0))
        neighbor=await self.source(NEIGHBOR,0,1,(0,None,None,None))
        await self.teach(neighbor,NEIGHBOR,0)
        await self.source(NEIGHBOR,0,1,(1,0,3,0))
        teacher=await self.source(p.teacher_pc,p.history,0,
            p.old if p.profile=='provider-promotion' else (0,None,None,None))
        await self.source(PC,p.history,0,p.old)
        return teacher

    async def offered(self,monitor):
        async def wait():return await monitor.offered
        waiter=asyncio.create_task(wait())
        try:
            event=await AnyOf(TaskComplete(waiter),SimTimeout(64,clock=self.agent.dut.clock))
            if event.kind is XEventKind.TIMEOUT:raise TimeoutError('no original raw-feedback offer boundary')
            self.agent.reference.raise_failure()
            return event.value
        finally:
            if not waiter.done():
                waiter.cancel()
                with suppress(asyncio.CancelledError):await waiter

    async def run(self):
        agent,p,coverage=self.agent,self.program,self.coverage
        teacher=await self.prepared()
        accepted=agent.reference.model.accepted_feedback
        monitor=ReadLifetimeMonitor(agent).start()
        task=None
        try:
            self.checks.check(p.protection(after=False),monitor.all_protection(),'complete reset-derived state before concurrent learning')
            coverage.reach('normally-learned-distinct-prestate')
            tx=UtageTraining(p.teacher_pc,POSITION,p.actual,deepcopy(teacher.meta),mispredict=1)
            self.checks.phase='original feedback and query lifetime'
            trigger=None
            if p.relation=='read-with-write':
                monitor.arm()
                task=asyncio.create_task(agent.training_driver.send(agent.compact_training(tx)))
                trigger=await self.offered(monitor)
            else:
                await agent.train(tx)
            transfer=agent.submit_predict(PC,POSITION,0,folded_history=p.history)
            original=await transfer
            if task is not None:await task
            await agent.training_activity.wait_idle('pipeline')
            agent.reference.raise_failure()
            self.checks.check(1,len(monitor.public),'one actual complete original raw feedback, not a replay')
            self.checks.check(UtageUsefulChecker._payload(tx),monitor.public[0]['bits'],'original PC, history and full source metadata')
            self.checks.check(1,agent.reference.model.accepted_feedback-accepted,'exactly one qualified original feedback')
            coverage.reach('complete-original-feedback',tick=monitor.public[0]['tick'])
            self.checks.check(1,len(monitor.effects),'one actual original learning-effect boundary')
            read=monitor.at(transfer.accepted_event.tick+2)
            response=monitor.at(transfer.accepted_event.tick+4)
            effect=monitor.effects[0]
            self.evidence.update(boundary=dict(accepted_tick=transfer.accepted_event.tick,read_tick=read['tick'],
                response_tick=response['tick'],effect_tick=effect['tick'],trigger=trigger,
                native_changes=effect['native'].get('changes',()),logical_effects=effect['effects']))
            self.checks.lifetime(read,response,effect)
            coverage.reach('actual-read-effect-relation',read_tick=read['tick'],effect_tick=effect['tick'])
            coverage.reach('original-read-not-rebound')
            self.checks.check(p.expected,values(original),'returned transfer owns the declared response version')
            coverage.reach('declared-response-version')
            self.sources.append((original,deepcopy(original.meta)))
            self.checks.phase='fresh new-version consumers'
            await self.source(PC,p.history,0,p.new)
            if p.profile=='different-identity-replacement':
                await self.source(p.teacher_pc,p.history,0,(1,0,4,1))
            coverage.reach('fresh-new-version-consumers')
            await self.source(NEIGHBOR,0,1,(1,0,3,0))
            self.checks.check(p.protection(after=True),monitor.all_protection(),'all1024 actual protection cells retain only declared changes')
            coverage.reach('all-other-protection-and-neighbor-preserved')
            self.checks.check(True,all(source.meta==saved for source,saved in self.sources),'all original complete source metadata remains immutable')
            coverage.reach('immutable-originals')
            agent.reference.raise_failure()
            self.evidence.update(status='PASS',completed=list(RULES),public=monitor.public,
                qualified_feedback=agent.reference.model.accepted_feedback-accepted,
                exact_read_tuple_retained=True,original_sources=len(self.sources),
                reference_checked=agent.reference.board.status.checked,reference_failed=agent.reference.board.status.failed)
            coverage.finish()
        finally:
            if task is not None:
                if not task.done():task.cancel()
                with suppress(asyncio.CancelledError):await task
            await monitor.aclose()


async def run_late_replacement(agent,program,coverage,evidence):
    from suites.frontend.bpu.utage.checker.read_lifetime import LateReplacementChecks
    from suites.frontend.bpu.utage.monitor.selective_protection import Monitor
    from suites.frontend.bpu.utage.model.read_lifetime import REBUILD_RULES

    await agent.reset()
    checks=LateReplacementChecks(program)
    monitor=Monitor(agent).start()
    accepted=agent.reference.model.accepted_feedback
    held={}
    consumers=[]

    async def source(spec,expected=None):
        transfer=agent.submit_predict(spec.pc,POSITION,spec.base,folded_history=spec.history,
            index_pc=spec.read_pc,index_history=spec.history)
        actual=await transfer
        token=checks.source(spec,transfer,actual,expected)
        return token,actual

    def transaction(step,original):
        predicted=step.source.base if step.source.counter is None else int(step.source.counter>=4)
        return UtageTraining(step.source.pc,POSITION,step.actual,deepcopy(original.meta),mispredict=int(predicted!=step.actual))

    async def consume(after_a):
        boundary=monitor.records[-1]['tick']
        for spec,expected in program.consumers(after_a=after_a):
            token,actual=await source(spec,expected)
            checks.check(True,checks.originals[token]['accepted']>boundary,'a genuinely new consumer follows the actual completed write')
            consumers.append(dict(phase='after-A' if after_a else 'after-B',pc=spec.pc,history=spec.history,
                accepted=checks.originals[token]['accepted'],expected=expected,actual=values(actual)))

    try:
        checks.check(program.protection_after(0),monitor.all_protection(),'all learning starts from the normal reset state')
        for step in program.steps[:-2]:
            checks.phase=step.name
            if step.name=='B-enter':
                held['old-A-return']=await source(program.old_a)
                coverage.reach('normally-released-original')
            token,original=await source(step.source)
            tx=transaction(step,original)
            checks.owned_feedback(step,token,tx)
            await agent.train(tx)
            checks.prefix(monitor,step.ordinal+1)
        held['old-B-return']=await source(program.old_b)
        a,b=(checks.originals[held[name][0]] for name in ('old-A-return','old-B-return'))
        checks.check(True,a['completed']<monitor.records[next(s.ordinal for s in program.steps if s.name=='B-enter')]['tick']<b['accepted'],
            'old A really predates replacement while old B comes from the distinct strengthened current owner')
        checks.check(a['spec'].indices[0],b['spec'].indices[0],'the two real originals compete for the same short row')
        from suites.frontend.bpu.utage.model.semantic import Context,tag
        checks.check(True,tag(a['spec'].pc,Context.from_recent(a['spec'].history),0)!=
            tag(b['spec'].pc,Context.from_recent(b['spec'].history),0),'complete logical tags remain different without truncation')
        for rule in ('real-distinct-originals','same-short-row-distinct-complete-tags','strong-different-current-owner'):coverage.reach(rule)
        late=program.steps[-2:]
        if program.mode=='adjacent':
            transactions=[]
            for step in late:
                token,original=held[step.name]
                tx=transaction(step,original);checks.owned_feedback(step,token,tx);transactions.append(tx)
            await agent.train_many(tuple(transactions))
            checks.prefix(monitor,len(program.steps))
        else:
            for step in late:
                checks.phase=step.name
                token,original=held[step.name]
                tx=transaction(step,original);checks.owned_feedback(step,token,tx)
                await agent.train(tx)
                checks.prefix(monitor,step.ordinal+1)
                if step.name=='old-A-return':await consume(True)
        for rule in ('old-source-counter-reconstruction','second-old-source-counter-reconstruction','both-complete-retag-writes'):coverage.reach(rule)
        delta=checks.cadence(monitor)
        coverage.reach('actual-requested-feedback-cadence',actual_tick_delta=delta)
        checks.phase='new consumers after both old returns'
        await consume(False)
        coverage.reach('fresh-short-and-long-consumers')
        coverage.reach('original-allocation-view-survives-overlap')
        checks.check(program.protection_after(len(program.steps)),monitor.all_protection(),'neighbor and every other protection cell survive both late retags')
        coverage.reach('neighbor-and-complete-protection-preserved')
        failures=getattr(program,'failed_allocations',int(program.mode=='serial'))
        checks.check((failures,failures),(agent.reference.model.low_tick,agent.reference.model.high_tick),
            'serial second feedback sees protection; adjacent original allocation read predates its predecessor write')
        checks.check(len(program.steps),agent.reference.model.accepted_feedback-accepted,'every original feedback is semantically accepted once')
        checks.finish(monitor)
        agent.reference.raise_failure()
        if monitor.failure is not None:raise monitor.failure
        coverage.reach('immutable-originals')
        coverage.finish()
        evidence.update(status='PASS',completed=list(REBUILD_RULES),actual_learning=monitor.records,
            feedback_receipts=[dict(tick=row['tick']) for row in monitor.public],late_feedback_tick_delta=delta,
            original_sources=len(checks.originals),consumers=consumers,actual_feedbacks=len(monitor.public),
            all_protection_cells_compared=1024,all_original_metadata_immutable=True,
            reference_checks=agent.reference.board.status.checked,reference_failures=agent.reference.board.status.failed)
    except BaseException as error:
        evidence.update(status='FAIL',phase=checks.phase,error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]],
            observed_learning=monitor.records,observed_public_feedbacks=len(monitor.public),sent_steps=checks.sent,consumers=consumers)
        raise
    finally:await monitor.aclose()
