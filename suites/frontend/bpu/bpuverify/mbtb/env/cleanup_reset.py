"""Normal old-metadata training, effective reset and fresh independent learning."""
from copy import deepcopy

from bpuverify.mbtb.transaction.types import MbtbBatchTraining,MbtbBranchFeedback
from bpuverify.mbtb.env.full_capacity_learning import planned_payload,observed_payload
from bpuverify.mbtb.checker.cleanup_reset import Checks
from bpuverify.mbtb.monitor.cleanup_reset import CleanupMonitor


class CleanupReset:
    def __init__(self,agent,program,coverage,evidence):
        self.agent,self.program,self.coverage,self.evidence=agent,program,coverage,evidence
        self.checks=Checks(program)
        self.snapshots=[]

    async def predict(self,pc):
        value=await self.agent.predict(pc)
        self.agent.reference.raise_failure()
        self.snapshots.append((value,deepcopy(value)))
        return value

    async def teach(self,branch,source,*,taken=True,allocate=True):
        request=MbtbBatchTraining(branch.pc,deepcopy(source.meta_entries),(
            MbtbBranchFeedback(branch.target,int(taken),branch.position,branch.kind,0,int(allocate)),))
        before=self.agent.reference.input_tick
        await self.agent.train_batch(request)
        actual=[(tick,feedback) for tick,feedback in self.agent.reference.accepted_feedback if tick>before]
        self.checks.check(1,len(actual),'one genuine feedback input')
        self.checks.check(planned_payload(request),observed_payload(actual[0][1]),
            'all original metadata and declared branch outcome reach the real input')
        self.evidence.setdefault('feedback',[]).append(dict(tick=actual[0][0],payload=observed_payload(actual[0][1])))

    async def run(self):
        agent,program,checks=self.agent,self.program,self.checks
        await agent.reset()
        monitor=CleanupMonitor(agent).start()
        try:
            old=await self.predict(program.old.pc)
            neighbor=await self.predict(program.neighbor.pc)
            checks.cold(old);checks.cold(neighbor)
            floor=len(agent.reference.accepted_cleanup)
            async with agent.defer_multi_hit_cleanup():
                await self.teach(program.old,old)
                await self.teach(program.neighbor,neighbor)
                checks.resident(await self.predict(program.old.pc),program.old,counter=2)
                checks.resident(await self.predict(program.neighbor.pc),program.neighbor,counter=2)
                await self.teach(program.changed,old)
                duplicate=await self.predict(program.old.pc)
                checks.duplicate(duplicate)
                self.coverage.reach('genuine-distinct-target-duplicate',tick=agent.reference.input_tick+1)
                monitor.arm()
                native=(await agent.expose_registered_invalidation(monitor)
                    if program.profile=='registered-invalidation' else monitor.status())
                receipts=list(agent.reference.accepted_cleanup)[floor:]
                checks.stage(receipts,native)
                self.evidence['old_cleanup']=dict(receipts=receipts,native=native)
                status=agent.prediction_scoreboard.status
                checks.check((0,0),(status.pending,status.processing),'no old response handle is abandoned by reset')
                self.coverage.reach('old-cleanup-stage-qualified',profile=program.profile,receipts=len(receipts),
                    native_registered=bool(native['clears']))
                checks.phase='effective reset and new execution'
                launch=monitor.status()
                checks.stage(receipts,launch)
                self.evidence['reset_launch']=launch
                await agent.reset()
                monitor.status()
                checks.check(True,monitor.reset is not None,'actual consumed reset observed')
                reset=monitor.reset
                checks.check(True,reset['tick']>native['tick'],'effective reset follows the declared old phase')
                state=reset['independent_state']
                checks.check((0,(),None),(state['populated_cells'],state['deferred_cleanup'],state['offered']),
                    'reset clears old residents, deferred clears and accepted learning')
                checks.check((0,0),(sum(state['entry_pending'].values()),sum(state['counter_pending'].values())),
                    'reset ends all independent pending branch/counter versions')
                self.evidence['effective_reset']=reset
                self.coverage.reach('effective-reset-ends-old-obligation',tick=reset['tick'])
                for pc in (program.old.pc,program.neighbor.pc):checks.cold(await self.predict(pc))
            await agent.training_activity.wait_idle()
            for pc in (program.neighbor.pc,program.old.pc):checks.cold(await self.predict(pc))
            self.coverage.reach('fresh-queries-have-no-old-identities',tick=agent.reference.input_tick+1)
            for branch in (program.new,program.new_neighbor):
                source=await self.predict(branch.pc)
                checks.cold(source)
                await self.teach(branch,source)
            checks.resident(await self.predict(program.new.pc),program.new,counter=2)
            self.coverage.reach('same-address-new-branch-survives',tick=agent.reference.input_tick+1)
            source=await self.predict(program.new.pc)
            await self.teach(program.new,source,taken=False,allocate=False)
            checks.resident(await self.predict(program.new.pc),program.new,counter=1)
            self.coverage.reach('new-direction-learning-is-independent',tick=agent.reference.input_tick+1)
            for order in ((program.new,program.new_neighbor),(program.new_neighbor,program.new)):
                for branch in order:checks.resident(await self.predict(branch.pc),branch,counter=1 if branch.kind==1 else 2)
            for actual,frozen in self.snapshots:checks.check(frozen,actual,'all old and new public snapshots remain immutable')
            self.coverage.reach('new-neighbor-and-old-snapshots-preserved',snapshots=len(self.snapshots))
            self.coverage.finish()
            self.evidence.update(status='PASS',completed=sorted(self.coverage.completed),
                reference_checked=agent.reference.board.status.checked,reference_failed=agent.reference.board.status.failed)
        finally:await monitor.aclose()
