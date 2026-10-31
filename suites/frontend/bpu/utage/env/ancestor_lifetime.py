"""Normal preparation reused; concurrent query carries two explicit ancestors."""
import asyncio
from contextlib import suppress
from copy import deepcopy

from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.env.read_lifetime import ReadLifetime
from suites.frontend.bpu.utage.monitor.read_lifetime import ReadLifetimeMonitor
from suites.frontend.bpu.utage.checker.read_lifetime import values
from suites.frontend.bpu.utage.model.ancestor_lifetime import PC,POSITION,NEIGHBOR,MATCH_PC,MATCH_HISTORY,RULES
from suites.frontend.bpu.utage.checker.ancestor_lifetime import Checks


class AncestorLifetime(ReadLifetime):
    def __init__(self,agent,program,coverage,evidence):
        super().__init__(agent,program,coverage,evidence)
        self.checks=Checks(program)

    async def source(self,pc,history,base,expected,*,read_pc=None,read_history=None):
        source=await self.agent.predict(pc,POSITION,base,folded_history=history,
            index_pc=read_pc,index_history=read_history)
        self.checks.check(expected,values(source),'normal source with explicit read and match ancestry')
        self.sources.append((source,deepcopy(source.meta)))
        return source

    async def later(self,expected):
        return await self.source(MATCH_PC,MATCH_HISTORY,0,expected,read_pc=PC,read_history=self.program.history)

    async def run(self):
        agent,p,coverage=self.agent,self.program,self.coverage
        teacher=await self.prepared()
        own_before=await self.source(MATCH_PC,MATCH_HISTORY,0,(0,None,None,None))
        later_before=await self.later(p.old)
        coverage.reach('distinct-read-and-match-contexts')
        accepted=agent.reference.model.accepted_feedback
        monitor=ReadLifetimeMonitor(agent).start()
        task=None
        try:
            self.checks.check(p.protection(after=False),monitor.all_protection(),'complete normal prestate, not output-seeded expected storage')
            coverage.reach('normally-learned-distinct-prestate')
            tx=UtageTraining(p.teacher_pc,POSITION,p.actual,deepcopy(teacher.meta),mispredict=1)
            trigger=None
            self.checks.phase='original feedback meets two-ancestor query'
            if p.relation=='read-with-write':
                monitor.arm()
                task=asyncio.create_task(agent.training_driver.send(agent.compact_training(tx)))
                trigger=await self.offered(monitor)
            else:await agent.train(tx)
            transfer=agent.submit_predict(MATCH_PC,POSITION,0,folded_history=MATCH_HISTORY,
                index_pc=PC,index_history=p.history)
            original=await transfer
            if task is not None:await task
            await agent.training_activity.wait_idle('pipeline')
            agent.reference.raise_failure()
            self.checks.check(1,len(monitor.public),'one actual original raw feedback')
            self.checks.check(UtageUsefulChecker._payload(tx),monitor.public[0]['bits'],'complete original teacher input and metadata')
            self.checks.check(1,agent.reference.model.accepted_feedback-accepted,'one independently qualified original learning')
            coverage.reach('complete-original-feedback',tick=monitor.public[0]['tick'])
            self.checks.check(1,len(monitor.effects),'one learning effect, not an idle equal-PC sample')
            read=monitor.at(transfer.accepted_event.tick+2)
            response=monitor.at(transfer.accepted_event.tick+4)
            effect=monitor.effects[0]
            self.evidence.update(boundary=dict(accepted_tick=transfer.accepted_event.tick,read_tick=read['tick'],
                response_tick=response['tick'],effect_tick=effect['tick'],trigger=trigger,
                native_changes=effect['native'].get('changes',()),logical_effects=effect['effects']),
                contexts=dict(read_pc=read['events'].read_pc,read_history=read['events'].read_context.folds,
                    read_indices=read['read'].indices,match_pc=response['frame'].pc,
                    match_history=response['frame'].context.folds,
                    public_indices=tuple(original.meta['readIndex']) if original.hit else None,
                    public_history=tuple(row['foldedHist'] for row in original.meta['foldedPathHistForTrain_hist']) if original.hit else None))
            self.checks.lifetime(read,response,effect)
            coverage.reach('actual-read-effect-relation',read_tick=read['tick'],effect_tick=effect['tick'])
            coverage.reach('original-read-not-rebound')
            self.checks.check(p.expected,values(original),'returned transfer has the checked original version')
            coverage.reach('declared-response-version')
            self.sources.append((original,deepcopy(original.meta)))
            self.checks.phase='fresh two-ancestor and own-context consumers'
            later_after=await self.later(p.new)
            coverage.reach('fresh-new-version-consumers')
            own_after=await self.source(MATCH_PC,MATCH_HISTORY,0,(0,None,None,None))
            coverage.reach('own-context-stays-cold')
            await self.source(NEIGHBOR,0,1,(1,0,3,0))
            self.checks.check(p.protection(after=True),monitor.all_protection(),'all1024 cells and unrelated branch preserved')
            coverage.reach('all-other-protection-and-neighbor-preserved')
            self.checks.check(True,all(source.meta==saved for source,saved in self.sources),'all original source metadata immutable')
            coverage.reach('immutable-originals')
            agent.reference.raise_failure()
            self.evidence.update(status='PASS',completed=list(RULES),public=monitor.public,
                qualified_feedback=agent.reference.model.accepted_feedback-accepted,
                exact_read_tuple_retained=True,original_sources=len(self.sources),
                consumers=dict(own_before=values(own_before),later_before=values(later_before),
                    original=values(original),later_after=values(later_after),own_after=values(own_after)),
                reference_checked=agent.reference.board.status.checked,reference_failed=agent.reference.board.status.failed)
            coverage.finish()
        finally:
            if task is not None:
                if not task.done():task.cancel()
                with suppress(asyncio.CancelledError):await task
            await monitor.aclose()
