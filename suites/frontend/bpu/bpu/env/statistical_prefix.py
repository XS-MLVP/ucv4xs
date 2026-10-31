"""Normal driver operations; no forced SRAM or per-signal test-case plumbing."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.env.branch_targets import BranchTargetProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.pipeline import Outcome, Resolution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.statistical_joint_sources import StatisticalJointSources
from suites.frontend.bpu.bpu.model.statistical_prefix import conditional_outcomes
from suites.frontend.bpu.bpu.monitor.unexecuted_indirect import actual_target_guard
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining, BpuBranchFeedback
from suites.frontend.bpu.tage.model.semantic import TABLES


class Program(BranchTargetProgram):
    @property
    def checks(self):
        return self.checker.coverage

    async def controls(self, **values):
        await self.pause()
        await self.agent.configure_predictors(**values, settle=True)
        await self.pause()

    async def query(self, pc):
        await self.pause()
        boundary = await RecoveryDriver(self.agent, self.checker).send(self.anchor,
            position=self.checks.program.recovery_offset, branch_type=int(Kind.INDIRECT), target=pc)
        receipt = await self.agent.next_transaction(start_pc=pc, after_tick=boundary)
        self.checks.save(receipt)
        await self.pause()
        return receipt

    async def feedback(self, receipt, *outcomes, maximum=False):
        await self.pause()
        token = self.checks.save(receipt)
        transaction = BpuBatchTraining(token.pc, receipt.meta.resolve, tuple(BpuBranchFeedback(
            b.position, b.target, int(b.kind), taken=int(b.taken), mispredict=int(b.mispredict)) for b in outcomes))
        self.checker.plan_feedback(receipt, transaction)
        if maximum:
            request = Resolution(token.history, token.pc, tuple(outcomes), origin=token)
            feedback = self.checks.bank.feedback_for(request)
            attempts = 0
            def admitted(_):
                nonlocal attempts
                self.checker.raise_failure()
                attempts += 1
                value = self.checks.bank.tage.allocation_at_next_accept(feedback)
                if value is not None and value[0] == TABLES - 1:
                    return True
                if attempts >= 128:
                    raise TimeoutError('highest-history semantic allocation admission budget')
                return False
            with self.agent.training_driver.admit_when(admitted):
                await self.agent.train_batch(transaction)
        else:
            await self.agent.train_batch(transaction)
        await self.pause()
        accepted = self.checker.resolutions_for_source(receipt)
        self.checks.check(1, len(accepted), 'one distinct original owns one actual accepted feedback')
        self.checks.check(tuple(outcomes), tuple(b for b in accepted[0][1].branches if b is not None),
            'actual accepted execution prefix remains exactly the declared one')
        return accepted[0][1]

    async def conditional(self, receipt, taken, *, maximum=False):
        token = self.checker.source_token(receipt)
        late = self.checks.bank.statistical_snapshot(token, resolved=True).late
        return await self.feedback(receipt, *conditional_outcomes(token, late, self.checks.program, taken), maximum=maximum)


@asynccontextmanager
async def experiment(agent, checks, *, program_type=Program,binding_factory=None):
    observation = PipelineObservation(agent, checks, sources=StatisticalJointSources(),binding_factory=binding_factory)
    checks.pipeline = observation.checker
    phr = BpuPhrChecker(scope='autonomous SC read and original execution-prefix selection', record_limit=8)
    async with observation, agent.observe_phr(phr), actual_target_guard(agent, checks):
        await agent.reset(checks.program.a)
        anchor = await agent.next_transaction(start_pc=checks.program.a)
        await agent.set_ready(prediction=False, meta=True)
        await agent.configure_predictors(ubtb=False, abtb=True, mbtb=True, tage=False,
            sc=False, ittage=True, ras=False, settle=True)
        env = program_type(agent, observation, anchor, checks.program.a)
        # Main owns a genuinely enabled cold read; predictor controls settle
        # before this normal reset, just as in the existing source programs.
        await env.pause()
        await agent.reset(checks.program.a)
        await agent.set_ready(prediction=True, meta=True)
        env.anchor = await agent.next_transaction(start_pc=checks.program.a)
        checks.save(env.anchor)
        await env.pause()
        yield env
        phr.summary()


class ContextProgram(Program):
    """Uninterrupted real prefix and jump before the measured branch."""
    async def probe_invalid_history(self,source):
        from copy import deepcopy
        from suites.frontend.bpu.bpu.model.selection import fallthrough
        c,p=self.checks,self.checks.program
        await self.pause()
        before=deepcopy(c.bank.sc.memory),c.bank.sc.thresholds.values
        accepted=c.open_warm_query(source)
        # Resume ordinary instructions before the already learned jump. Their
        # genuine S3 completions revalidate the restored conditional history.
        # Close flow on actual acceptance of the jump predecessor. Its normal
        # Main correction still issues the target while ready is closed; this
        # leaves the warm query held without relying on a late S0 reaction.
        stride=fallthrough(p.jump).branch.target-p.jump
        entry=p.jump-stride*(len(self.checker.model.stages)+1)
        await RecoveryDriver(self.agent,self.checker).send(source,position=0,target=entry,until=accepted)
        await self.pause()
        token=c.warm_query['token']
        c.check(True,token is not None,'normal predecessor correction issued the declared warm query')
        c.check(True,token is self.checker.model.stages[0],'warm original remains held before normal cancellation')
        read=c.bank.statistical_snapshot(token).read
        proof=self.checker.sc_numeric_checked.get(token.history.sequence,{})
        c.check({'read'},set(proof),'cancelled warm query has its full actual read but no consumption')
        # Disabling SC suppresses new table reads without changing its learned
        # weights. Recover via public metadata, then flush the disabled query
        # before consuming a freshly re-enabled, invalid-history original.
        await self.controls(sc=False)
        self.anchor=await Program.query(self,p.a)
        c.invalid_history.begin_window(proof['read'])
        await self.controls(sc=True)
        self.anchor=await Program.query(self,p.a)
        invalid=c.save(self.anchor)
        c.check(False,c.bank.statistical_snapshot(invalid).read.context.common_valid,
            'new original genuinely has invalid conditional history')
        numeric=c.numeric_consumer(self.anchor)
        c.check(before,(c.bank.sc.memory,c.bank.sc.thresholds.values),'read cancellation and control changes do not train SC')
        c.invalid_history_probe=dict(warm_owner=token.sequence,warm_read_tick=proof['read'],
            warm_history_indices=read.indices[2:6],warm_history_weights=read.weights[2:6],
            cancelled_before_consumption=True,invalid_consumer=numeric,
            no_extra_backend_training=True,learned_SC_state_unchanged=True)

    async def query(self,pc):
        p=self.checks.program
        if pc!=p.b:
            return await super().query(pc)
        prefix=await super().query(p.prefix)
        await self.agent.set_ready(prediction=True,meta=True)
        source=await self.agent.next_transaction(start_pc=pc,after_tick=prefix.prediction_tick)
        self.checks.save(source)
        await self.pause()
        return source

    async def conditional(self,source,taken,*,maximum=False):
        token=self.checks.save(source)
        late=self.checks.bank.statistical_snapshot(token,resolved=True).late
        return await self.feedback(source,self.checks.program.outcome(token,late,taken),maximum=maximum)

    async def context_feedback(self,source,taken,label):
        await self.controls(tage=False)
        self.checks.begin_context_feedback(source,taken,label)
        request=await self.conditional(source,taken)
        self.checks.end_context_feedback(request)
        await self.controls(tage=True)
        return request


class ConcurrentContextProgram(ContextProgram):
    async def query(self,pc):
        # The separate aligned anchor has a real zero-contribution return
        # edge. Refresh its original before each excursion, so both bounded
        # checkpoint age and reproducible path context hold without reset.
        if pc!=self.checks.program.a:
            self.anchor=await super().query(self.checks.program.a)
        return await super().query(pc)

    async def context_feedback(self,source,taken,label):
        c,p=self.checks,self.checks.program
        await self.controls(tage=False,ubtb=False)
        # This recent genuine owner keeps recovery within retained history;
        # an arbitrarily old reset checkpoint is not a legal substitute.
        self.anchor=await self.query(p.a)
        await self.controls(ubtb=True)
        c.stream=True
        await RecoveryDriver(self.agent,self.checker).send(self.anchor,
            position=p.recovery_offset,branch_type=int(Kind.INDIRECT),target=p.loop)
        await self.observation.wait('SC_nonzero_context_independent_stream',lambda _:c.steady>=2)
        c.begin_context_feedback(source,taken,label)
        token=c.save(source)
        late=c.bank.statistical_snapshot(token,resolved=True).late
        outcome=p.outcome(token,late,taken)
        transaction=BpuBatchTraining(token.pc,source.meta.resolve,(BpuBranchFeedback(
            outcome.position,outcome.target,int(outcome.kind),taken=int(outcome.taken),
            mispredict=int(outcome.mispredict)),))
        self.checker.plan_feedback(source,transaction)
        transfer=self.agent.training_driver.send(transaction)
        if p.blocks(c.probe['needs_read']):
            await self.observation.wait('SC_old_nonzero_context_held',lambda _:c.arbitration['blocked']>=2)
            c.check(None,transfer.accepted_event,'old feedback remains pending until actual conflict release')
            await self.agent.set_ready(prediction=False,meta=True)
        accepted=await transfer
        await self.pause()
        c.stream=False
        resolutions=self.checker.resolutions_for_source(source)
        c.check(1,len(resolutions),'concurrent original receives exactly one complete feedback')
        request=resolutions[0][1]
        c.end_concurrent_feedback(request,accepted)
        # Drain the held loop read with an ordinary recovery before changing
        # MicroBTB enable. Its registered response belongs to that old read,
        # not to a new disabled lookup at an otherwise held S1 boundary.
        self.anchor=await self.query(p.a)
        await self.controls(tage=True,ubtb=False)
        return request
