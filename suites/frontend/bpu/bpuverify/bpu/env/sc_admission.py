"""Submit through the async driver; stop on actual witnesses, never fixed waits."""
from contextlib import asynccontextmanager
from bpuverify.bpu.bundle.main_duplicate_cleanup import binding as main_learning_binding
from bpuverify.bpu.monitor.service import ServiceMonitor,MainLearningReceipts
from bpuverify.bpu.env.statistical_prefix import Program as PrefixProgram
from bpuverify.bpu.model.pipeline import Resolution
from bpuverify.bpu.model.statistical_prefix import conditional_outcomes
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.transaction.types import BpuBatchTraining,BpuBranchFeedback


@asynccontextmanager
async def main_learning_evidence(env,evidence):
    receipts = MainLearningReceipts(env.checker)
    try:
        async with ServiceMonitor(env.agent,receipts,binding=main_learning_binding(env.agent)):
            yield receipts
    finally:
        evidence['main_learning_receipts'] = receipts.state()


class Program(PrefixProgram):
    def feedback_outcomes(self, token, taken):
        late=self.checks.bank.statistical_snapshot(token,resolved=True).late
        return conditional_outcomes(token,late,self.checks.program,taken)

    async def start_stream(self):
        c,p = self.checks,self.checks.program
        await self.pause()
        c.stream = True
        # Keep the stream flowing after normal recovery. Capturing and pausing
        # an extra loop transaction here only consumes retained history before
        # the experiment; it is not a protocol requirement.
        await RecoveryDriver(self.agent,self.checker).send(self.anchor,
            position=p.recovery_offset,branch_type=int(Kind.INDIRECT),target=p.loop)
        await self.observation.wait('SC_continuous_independent_prediction_stream',lambda _:c.steady>=2,timeout_cycles=256)

    async def stream_feedback(self,source):
        await self.start_stream()
        c,p = self.checks,self.checks.program
        token = c.save(source)
        late = c.bank.statistical_snapshot(token,resolved=True).late
        outcomes = conditional_outcomes(token,late,p,p.actual_taken)
        resolution = Resolution(token.history,token.pc,tuple(outcomes),origin=token)
        transaction = BpuBatchTraining(token.pc,source.meta.resolve,tuple(BpuBranchFeedback(
            b.position,b.target,int(b.kind),taken=int(b.taken),mispredict=int(b.mispredict)) for b in outcomes))
        c.begin(source,resolution)
        self.checker.plan_feedback(source,transaction)
        pending = self.agent.training_driver.send(transaction)
        if p.blocked:
            await self.observation.wait('SC_actual_read_conflict_held',lambda _:len(c.blocked_ticks)>=2)
            c.check(None,pending.accepted_event,'driver remains unaccepted during actual SC conflict')
            await self.agent.set_ready(prediction=False,meta=True)
        accepted = await pending
        await self.pause()
        c.stream = False
        c.check([accepted.tick],c.accepted_ticks,'driver completion equals actual monitor acceptance')
        return accepted

    async def stream_feedbacks(self,sources):
        await self.start_stream()
        c,p = self.checks,self.checks.program
        resolutions,transactions = [],[]
        for source,taken in zip(sources,p.truths,strict=True):
            token = c.save(source)
            outcomes = self.feedback_outcomes(token,taken)
            resolutions.append(Resolution(token.history,token.pc,tuple(outcomes),origin=token))
            transactions.append(BpuBatchTraining(token.pc,source.meta.resolve,tuple(BpuBranchFeedback(
                b.position,b.target,int(b.kind),taken=int(b.taken),mispredict=int(b.mispredict)) for b in outcomes)))
        c.begin_many(sources,resolutions)
        for source,transaction in zip(sources,transactions,strict=True):
            self.checker.plan_feedback(source,transaction)
        handles = tuple(self.agent.training_driver.send(transaction) for transaction in transactions)
        if p.blocked:
            await self.observation.wait('SC_actual_queued_conflict_held',lambda _:len(c.blocked_ticks)>=2)
            c.check((None,)*len(handles),tuple(handle.accepted_event for handle in handles),
                'all driver submissions remain unaccepted behind the actual held head')
            await self.agent.set_ready(prediction=False,meta=True)
        accepted = tuple([(await handle).tick for handle in handles])
        await self.pause()
        c.stream = False
        c.check(accepted,tuple(c.accepted_ticks),'every driver receipt matches actual monitor acceptance')
        return accepted


class ContextBurstProgram(Program):
    """Independent real prefixes meet the same instruction, then queue results."""
    async def query(self, pc):
        if pc==self.checks.program.b:
            raise ValueError('select an explicit incoming context for the shared branch')
        if pc!=self.checks.program.a:
            self.anchor=await PrefixProgram.query(self,self.checks.program.a)
        return await PrefixProgram.query(self,pc)

    async def query_context(self, context):
        p=self.checks.program
        if not self.checks.bank.statistical_enabled:await self.controls(sc=True)
        self.anchor=await PrefixProgram.query(self,p.a)
        prefix=await PrefixProgram.query(self,p.prefix_for(context))
        await self.agent.set_ready(prediction=True,meta=True)
        from bpuverify.bpu.model.common_history import GHR_WIDTH
        # Select a public original by its independently forecast experience,
        # not by a live DUT history value or a fixed elapsed-cycle delay.
        for _ in range(GHR_WIDTH+len(self.checker.model.stages)+1):
            token=self.checks.save(prefix)
            history=self.checks.bank.queries.snapshot(token).metadata
            if history.valid and (history.ghr,history.bw)==(p.exit_history(context),p.exit_history(context)):
                break
            prefix=await self.agent.next_transaction(start_pc=p.loop_prefix,after_tick=prefix.prediction_tick)
        else:raise AssertionError('declared real loop experience was not published')
        await self.pause()
        boundary=await RecoveryDriver(self.agent,self.checker).send(prefix,position=2,
            branch_type=int(Kind.CONDITIONAL),taken=False,target=p.loop_prefix+16)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=p.b,after_tick=boundary)
        self.checks.save(source)
        await self.pause()
        return source

    def feedback_outcomes(self, token, taken):
        late=self.checks.bank.statistical_snapshot(token,resolved=True).late
        return (self.checks.program.outcome(token,late,taken),)

    async def conditional(self, source, taken, *, maximum=False, learn_sc=False):
        if not learn_sc:await self.controls(sc=False)
        result=await self.feedback(source,*self.feedback_outcomes(self.checks.save(source),taken),maximum=maximum)
        if not learn_sc:await self.controls(sc=True)
        return result

    async def sc_feedback(self, source, taken):
        await self.controls(tage=False)
        request=await self.conditional(source,taken,learn_sc=True)
        await self.controls(tage=True)
        return request

    async def return_from_stream(self):
        """Use a recent real source; recondition features without old restores."""
        from bpuverify.bpu.model.path_history import LAYOUT,SHIFT
        c,p=self.checks,self.checks.program
        c.close_submissions()
        recent=await self.agent.next_transaction(start_pc=p.loop,after_tick=c.overlap_ticks[-2])
        token=c.save(recent)
        age=self.checker.model.history.taken_edges-token.history.taken_edges
        return_tick=await RecoveryDriver(self.agent,self.checker).send(recent,target=p.a)
        root=await self.agent.next_transaction(start_pc=p.a,after_tick=return_tick)
        c.save(root)
        await self.pause()
        # A cold direct branch may execute and redirect before its training
        # arrives. Resolve each real published iteration normally. These
        # zero-contribution edges replace the finite feature history without
        # restoring an expired checkpoint or changing any predictor memory.
        width=max(length for length,_ in LAYOUT)
        budget=(width+SHIFT-1)//SHIFT+len(self.checker.model.stages)+1
        for used in range(1,budget+1):
            owner=c.save(root)
            if owner.history.history%(1<<width)==0:break
            boundary=await RecoveryDriver(self.agent,self.checker).send(root,position=0,
                branch_type=int(Kind.DIRECT),target=p.a)
            root=await self.agent.next_transaction(start_pc=p.a,after_tick=boundary)
            c.save(root)
            await self.pause()
        else:raise AssertionError('normal zero-contribution branches did not clear the finite feature history')
        self.anchor=root
        await self.controls(tage=True,ubtb=False)
        self.anchor=await PrefixProgram.query(self,p.a)
        c.check(0,c.save(self.anchor).history.history%(1<<width),'new root reproduces all prediction feature history bits')
        return dict(recent_stream_source=token.sequence,source_age_taken_edges=age,
            reconditioned_history_bits=width,real_zero_contribution_sources=used,
            no_expired_checkpoint_restored=True,no_reconditioning_training=True,
            Main_enable_unchanged=True)
