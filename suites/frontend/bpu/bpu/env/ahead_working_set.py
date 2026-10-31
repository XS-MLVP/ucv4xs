"""Normal feedback and owned recovery connect declared branch programs."""
from contextlib import asynccontextmanager

from suites.frontend.bpu.bpu.bundle.ahead_working_set import working_set_binding
from suites.frontend.bpu.bpu.checker.ahead_working_set import AheadWorkingSetChecks
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.env.branch_targets import BranchTargetProgram
from suites.frontend.bpu.bpu.env.pipeline import PipelineObservation
from suites.frontend.bpu.bpu.model.ahead_working_set import Edge
from suites.frontend.bpu.bpu.model.early_aging import require_recovery_window
from suites.frontend.bpu.bpu.model.early_direction_sources import EarlyDirectionSources
from suites.frontend.bpu.bpu.model.path_history import WIDTH, LAYOUT, SHIFT
from suites.frontend.bpu.bpu.model.selection import fallthrough
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback, BpuRedirect


class PrefixWorkingSetEnv(BranchTargetProgram):
    def __init__(self,agent,observation,anchor,program,checks):
        super().__init__(agent,observation,anchor,program.initial_pc)
        self.program,self.checks=program,checks

    async def query(self,pc):
        from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
        await self.pause()
        boundary=await RecoveryDriver(self.agent,self.checker).send(self.anchor,position=0,branch_type=3,target=self.pc)
        self.anchor=await self.agent.next_transaction(start_pc=self.pc,after_tick=boundary)
        self.checks.save(self.anchor)
        await self.pause()
        index=next((i for i in range(self.program.count) if self.program.pc(i)==pc),None)
        target=pc if index is None else self.program.predecessor(index).pc
        boundary=await RecoveryDriver(self.agent,self.checker).send(self.anchor,position=0,branch_type=3,target=target)
        source=await self.agent.next_transaction(start_pc=target,after_tick=boundary)
        self.checks.save(source)
        if index is not None:
            source=await self.agent.next_transaction(start_pc=pc,after_tick=source.prediction_tick)
            self.checks.save(source)
        await self.pause()
        return source

    async def feedback(self,source,*outcomes):
        result=await self.resolve(source,*(BpuBranchFeedback(b.position,b.target,int(b.kind),
            taken=int(b.taken),mispredict=int(b.mispredict)) for b in outcomes),retire=False)
        self.checks.accepted_prefix(source,result[1])
        return result[1]

    async def window_feedback(self,index,source,early,later):
        token=self.checks.save(source)
        choice=self.checker.model.sources.choose(token,3,self.checker.last_cycle.enabled).branch
        return await self.feedback(source,*self.program.outcomes(index,choice,early_taken=early,later_taken=later))

    async def establish(self,index,early,later):
        from suites.frontend.bpu.bpu.checker.ahead_working_set import prefix_main_counts
        # At most two three-step saturating-counter journeys, plus the next
        # fresh consumer. This is an outcome budget, never a cycle delay.
        for _ in range(9):
            source=await self.query(self.program.pc(index))
            counts=prefix_main_counts(self.checks.save(source))
            if counts.get(2)==(3 if early else 0) and (early or counts.get(12)==(3 if later else 0)):
                return source
            await self.window_feedback(index,source,early,later)
        raise AssertionError('real instruction feedback did not establish the declared directions')

    async def converge(self,index,counts):
        from suites.frontend.bpu.bpu.checker.ahead_working_set import prefix_consumer_matches,prefix_ahead_view
        for _ in range(16):
            source=await self.query(self.program.pc(index))
            token=self.checks.save(source)
            if prefix_consumer_matches(self.checker.model.sources,token,self.program,index,counts):return source
        raise AssertionError(('no complete original prefix consumer',index,counts,
            prefix_ahead_view(self.checker.model.sources,token)))

    async def prepare_prefixes(self):
        from suites.frontend.bpu.bpu.model.pipeline import Outcome
        from suites.frontend.bpu.bpu.model.selection import Kind
        from suites.frontend.bpu.bpu.checker.ahead_working_set import prefix_ahead_view
        for index in self.program.order:
            edge=self.program.predecessor(index)
            await self.feedback(await self.query(edge.pc),Outcome(edge.position,edge.target,Kind.DIRECT,True,mispredict=True))
            await self.window_feedback(index,await self.query(self.program.pc(index)),False,True)
            await self.window_feedback(index,await self.query(self.program.pc(index)),True,True)
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.pause()
        for index in self.program.order:
            for _ in range(6):
                source=await self.query(self.program.pc(index))
                view=prefix_ahead_view(self.checker.model.sources,self.checks.save(source))
                if 2 in view and view[2]['counter']==3:break
            else:raise AssertionError('no strong original early conditional')
            await self.establish(index,False,True)
            await self.converge(index,(0,3))


class AheadWorkingSetEnv(BranchTargetProgram):
    def __init__(self, agent, observation, anchor, program, checks):
        super().__init__(agent, observation, anchor, program.edges(0)[0].pc)
        self.program, self.checks, self.source = program, checks, anchor

    async def recover(self, source, edge, *, taken=True):
        if not taken and (edge.kind != 1 or edge.target != fallthrough(edge.pc).branch.target):
            raise ValueError('not-taken recovery must continue at the actual fetch fallthrough')
        await self.pause()
        token = self.checker.source_token(source)
        require_recovery_window(self.checker.model.history.taken_edges, token.history.taken_edges,
            capacity=WIDTH, history_bits=max(length for length, _ in LAYOUT), shift=SHIFT)
        request = BpuRedirect(edge.target, source.meta.redirect, cfi_pc=edge.cfi_pc,
                              taken=int(taken), branch_type=edge.kind)
        self.checker.plan_redirect(source, request)
        boundary = await self.agent.redirect(request)
        self.checks.redirect_receipts.append(dict(source_tick=source.meta_tick, accepted_tick=boundary,
                                                  pc=edge.pc, target=edge.target, taken=taken))
        await self.agent.set_ready(prediction=True, meta=True)
        result = await self.agent.next_transaction(start_pc=edge.target, after_tick=boundary)
        self.checker.source_token(result)
        await self.pause()
        self.release_unused(result)
        return result

    def release_unused(self, source):
        # Verification owners can retire after acceptance. Do not keep an
        # unbounded trace or choose a numeric checkpoint alias as an owner.
        for tick in tuple(self.checker.source_receipts):
            if tick != source.meta_tick:
                self.checker.retire_source(tick)

    async def prepare(self, cohort, source):
        self.checks.begin(cohort, 'prepare')
        for edge in self.program.edges(cohort):
            self.checks.check(edge.pc, source.prediction.start_pc, 'declared next cold/resident program source')
            event = await self.resolve(source, BpuBranchFeedback(edge.position, edge.target, edge.kind,
                taken=1, mispredict=1), retire=False)
            self.checks.accepted(source, event, edge)
            source = await self.recover(source, edge)
        self.source = source
        return source

    async def lap(self, cohort, phase):
        self.checks.begin(cohort, phase)
        await self.agent.set_ready(prediction=True, meta=True)
        def complete(_):
            return (self.checks.cohort_complete() and (phase != 'late-older-survivors'
                or set(self.checks.frozen_survivors) == self.checks.revisited_survivors))
        # This is a progress deadline, not settling stimulus: the phase ends
        # on actual qualified consumers. The bound scales with program length.
        await self.observation.wait('all_declared_'+phase+'_Ahead_consumers', complete,
            timeout_cycles=16*len(self.program.edges(cohort)))
        await self.pause()
        self.checks.close_lap()

    async def bridge_source(self, cohort):
        edge = self.program.edges(cohort)[-1]
        boundary = self.checker.current_event.tick
        await self.agent.set_ready(prediction=True, meta=True)
        source = await self.agent.next_transaction(start_pc=edge.pc, after_tick=boundary,
                                                   limit=4*len(self.program.edges(cohort)))
        self.checker.source_token(source)
        await self.pause()
        return source

    async def switch(self, current, following):
        source = await self.bridge_source(current)
        await self.agent.configure_predictors(abtb=False, settle=True)
        old = self.program.edges(current)[-1]
        bridge = Edge(old.pc, self.program.edges(following)[0].pc, 3, old.position)
        event = await self.resolve(source, BpuBranchFeedback(bridge.position, bridge.target, 3,
            taken=1, mispredict=1), retire=False)
        self.checks.accepted(source, event, bridge, bridge=True)
        return await self.recover(source, bridge)


@asynccontextmanager
async def ahead_working_set_env(agent, program, coverage, *, disabled_from_reset=None,
                                checks_factory=AheadWorkingSetChecks, environment_factory=AheadWorkingSetEnv):
    if disabled_from_reset not in (None, 'ubtb', 'tage'):
        raise ValueError('cold isolation supports MicroBTB or TAGE')
    checks = checks_factory(program, coverage)
    phr = BpuPhrChecker(scope='natural branch working set; owned Main/Ahead/MicroTAGE', record_limit=8)
    observation = PipelineObservation(agent, checks, sources=EarlyDirectionSources(),
                                      binding_factory=working_set_binding)
    checks.pipeline = observation.checker
    try:
        async with observation, agent.observe_phr(phr):
            if disabled_from_reset is not None:
                await agent.configure_predictors(**{disabled_from_reset: False})
            initial_pc=getattr(program,'initial_pc',program.edges(0)[0].pc)
            await agent.reset(initial_pc)
            anchor = await agent.next_transaction(start_pc=initial_pc)
            # Priming occurs while every predictor is genuinely cold. Both
            # MicroBTB's held fallback and TAGE's un-gated fast corrections
            # must receive that defined cold read before isolation. Disabling
            # their future reads from reset would preserve undefined outputs.
            await agent.configure_predictors(ubtb=False, abtb=False, mbtb=True, tage=False,
                sc=False, ittage=False, ras=False, settle=True)
            env = environment_factory(agent, observation, anchor, program, checks)
            await env.pause()
            yield env
            phr.summary()
    except BaseException as error:
        coverage.evidence = dict(checks.summary(), status='FAIL', first_error_type=type(error).__name__,
                                 first_error=str(error))
        raise
    else:
        coverage.evidence = dict(checks.summary(), status='PASS')
