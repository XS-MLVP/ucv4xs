"""Real source recovery, bounded normal learning and monitor-owned windows."""
from contextlib import asynccontextmanager
from bpuverify.common.model.configuration import RESULT_SLOTS

from bpuverify.bpu.bundle.history_working_set import history_working_set_binding
from bpuverify.bpu.checker.history_working_set import HistoryWorkingSetChecks
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.bpu.env.branch_targets import BranchTargetProgram
from bpuverify.bpu.env.pipeline import PipelineObservation
from bpuverify.bpu.model.ahead_working_set import Edge
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.model.early_opposition import resident
from bpuverify.bpu.model.history_working_set import ANCHOR, SHORT_POSITION, POSITION, FALLBACK
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.path_history import WIDTH, LAYOUT, SHIFT
from bpuverify.bpu.transaction.types import BpuBranchFeedback, BpuRedirect
from bpuverify.ubtb.model.semantic import UbtbReference


class HistoryWorkingSetEnv(BranchTargetProgram):
    def __init__(self, agent, observation, anchor, program, checks, *, anchor_pc=ANCHOR):
        super().__init__(agent,observation,anchor,anchor_pc)
        self.program,self.checks,self.source = program,checks,anchor
        self.final_position = SHORT_POSITION
        self.tail_variant = None
        self.installed_path = None

    def release_unused(self):
        for tick in tuple(self.checker.source_receipts):
            if tick != self.source.meta_tick:self.checker.retire_source(tick)

    async def go(self, source, edge):
        self.checks.check(edge.pc,source.prediction.start_pc,'real predecessor source owns its declared CFI')
        token = self.checker.source_token(source)
        require_recovery_window(self.checker.model.history.taken_edges,token.history.taken_edges,
            capacity=WIDTH,history_bits=max(length for length,_ in LAYOUT),shift=SHIFT)
        tx = BpuRedirect(edge.target,source.meta.redirect,cfi_pc=edge.cfi_pc,taken=1,branch_type=edge.kind)
        self.checker.plan_redirect(source,tx)
        # Preparation must not run an unintended lap while backend feedback
        # is being installed. Arm observation BEFORE recovery; the control
        # driver opens/closes flow on the actual target acceptance.
        accepted = self.checks.open_window(None,None,pc=edge.target)
        boundary = await self.agent.redirect(tx)
        following = await self.source_window(edge.target,accepted=accepted)
        self.checks.check(True,following.prediction_tick>=boundary,
                          'the next instruction is younger than its actual recovery')
        self.checks.path_recoveries += 1
        self.checks.redirect_receipts.append(dict(source_tick=source.meta_tick,accepted_tick=boundary,
            pc=edge.pc,target=edge.target,kind=edge.kind))
        self.checker.retire_source(source.meta_tick)
        return following

    async def feedback(self, source, edge, *, taken=True, mispredict=True):
        event = await self.resolve(source,BpuBranchFeedback(edge.position,edge.target,edge.kind,
            taken=int(taken),mispredict=int(mispredict)),retire=False)
        self.checks.accepted(source,event,edge,taken=taken)
        return event

    async def window(self, path=None, *, final_position=None):
        self.source = await self.source_window(self.pc,path=path,final_position=final_position)
        self.release_unused()
        return self.source

    async def source_window(self, pc, *, path=None, final_position=None, accepted=None):
        if accepted is None:accepted = self.checks.open_window(path,final_position,pc=pc)
        try:
            await self.agent.accept_predictions_until(accepted,name='owned-real-history-source',
                timeout_cycles=16*len(self.program.edges(0)),failure=lambda:self.checker.failure)
        except TimeoutError as error:
            cycle = self.checker.last_cycle
            error.add_note(repr(dict(phase=self.checks.phase,
                source_pc=self.source.prediction.start_pc,source_tick=self.source.meta_tick,
                installed=None if self.installed_path is None else self.installed_path.ordinal,
                main=self.checker.model.sources.main.lookup_snapshot(self.pc).values(),
                live_pcs=None if cycle is None else tuple(None if token is None else token.pc for token in cycle.tokens),
                next_pc=None if cycle is None else cycle.next_pc,
                recent=tuple(dict(tick=row['tick'],pcs=tuple(row['actual'].get(f'pc{i}') for i in range(1,4)),
                    choices=tuple(row['actual'].get(f'choice{i}') for i in range(1,4)))
                    for row in self.checker.records))))
            raise
        source = await self.agent.next_transaction(start_pc=pc,
            after_tick=self.checks.selected_tick-1,limit=16*len(self.program.edges(0)))
        self.checker.source_token(source)
        await self.pause()
        self.checks.close_window(source,path=path)
        return source

    async def fresh_anchor(self, position):
        # Main SRAM can be committed while the held younger request still
        # owns its OLD lookup. A newly closed program does not repair that
        # request. Resolve the genuine later branch from the exact original
        # source; do not infer forward progress from current table contents.
        await self.go(self.source,Edge(self.pc,self.program.helper.pcs[0],
            3 if position == FALLBACK else 1,position))
        return await self.window()

    def main_direction(self, source, position):
        token = self.checker.source_token(source)
        values = token.lookup.values()
        entries = [bool(values[f'{slot}.taken']) for slot in range(RESULT_SLOTS) if values.get(f'{slot}.valid')
            and values.get(f'{slot}.position') == position and values.get(f'{slot}.kind') == 1]
        self.checks.check(1,len(entries),'one original Main conditional owns the requested direction')
        return entries[0]

    def has_main(self, source, position):
        token = self.checker.source_token(source)
        return any(entry.hit and entry.position == position for row in source_entries(token.lookup) for entry in row)

    async def guide(self, position, *, taken, later):
        if type(taken) is not bool:raise ValueError('Main guidance requires an explicit actual direction')
        # Two real outcomes can cross a two-bit direction boundary. Stop as
        # soon as the program has the desired result; reaching a particular
        # internal confidence endpoint is not part of this scenario.
        for _ in range(3):
            if self.main_direction(self.source,position) == taken:return
            source = self.source
            await self.feedback(source,Edge(self.pc,self.program.helper.pcs[0],1,position),
                taken=taken,mispredict=True)
            await self.fresh_anchor(position if taken else later)
        raise AssertionError('normal original outcomes did not establish the declared Main direction')

    async def set_main(self, *, early=False, target=True):
        await self.pause()
        await self.agent.configure_predictors(abtb=False,settle=True)
        if early:
            await self.guide(SHORT_POSITION,taken=True,later=POSITION)
            self.final_position = SHORT_POSITION
            return
        await self.guide(SHORT_POSITION,taken=False,later=POSITION if target else FALLBACK)
        if not self.has_main(self.source,POSITION):
            await self.feedback(self.source,Edge(self.pc,self.program.helper.pcs[0],1,POSITION))
            await self.fresh_anchor(POSITION)
        await self.guide(POSITION,taken=target,later=FALLBACK)
        if not target and not self.has_main(self.source,FALLBACK):
            await self.feedback(self.source,Edge(self.pc,self.program.helper.pcs[0],3,FALLBACK))
            await self.fresh_anchor(FALLBACK)
        self.final_position = POSITION if target else FALLBACK

    async def bootstrap(self):
        self.checks.phase = 'normal-main-and-prefix-discovery'
        first,*prefix = self.program.edges(0)
        await self.feedback(self.source,first)
        source = await self.go(self.source,first)
        for edge in prefix:
            await self.feedback(source,edge)
            source = await self.go(source,edge)
        self.source = source
        await self.pause()
        self.release_unused()
        await self.guide(SHORT_POSITION,taken=True,later=POSITION)
        self.tail_variant = self.program.helper.tail_variant
        self.installed_path = self.program.helper
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.learn_until(self.program.helper,lambda source:
            self.ahead_counter(source,SHORT_POSITION) == 3,
            'original conditional has genuine strong early consumers')

    def cached_tail(self, path):
        model = self.checker.model.sources.micro
        for edge in path.edges()[5:]:
            slot = model._find(2*edge.pc)
            if slot is None:return False
            entry = model.entries[slot]
            if (entry.target,entry.position,entry.branch_type) != (
                    2*edge.target & model.target_mask,edge.position,edge.kind):return False
        return True

    async def prepare_tail(self, path):
        if self.tail_variant == path.tail_variant:return
        await self.agent.configure_predictors(abtb=False,settle=True)
        source = await self.go(self.source,Edge(self.pc,self.program.helper.pcs[0],
            3 if self.final_position == FALLBACK else 1,self.final_position))
        for edge in path.edges()[:4]:source = await self.go(source,edge)
        for edge in path.edges()[4:]:
            await self.feedback(source,edge)
            source = await self.go(source,edge)
        self.source = source
        await self.pause()
        self.release_unused()
        # Distinct original tail sites must actually be learned. Main target
        # correction can legitimately deplete an older MicroBTB confidence;
        # its published capacity/three-bit outcome bound controls progress.
        for _ in range(UbtbReference.confidence_max+2):
            if self.cached_tail(path):break
            await self.fresh_anchor(self.final_position)
        else:raise AssertionError('real tail outcomes failed to establish their early target owners')
        self.tail_variant = path.tail_variant
        self.installed_path = None

    async def predecessor(self, source, edge):
        """Install a changed program edge, then execute its actual recovery.

        An unchanged instruction needs no extra backend feedback. This uses
        the independent original lookup, never a bank/way or DUT state to
        select the next instruction. Concurrent feedback/recovery is not a
        prerequisite of the history-lifetime requirement.
        """
        values = self.checker.source_token(source).lookup.values()
        learned = any(values.get(f'{slot}.valid') and
            (values.get(f'{slot}.position'),values.get(f'{slot}.target'),values.get(f'{slot}.kind')) ==
            (edge.position,edge.target,edge.kind) for slot in range(RESULT_SLOTS))
        if not learned:await self.feedback(source,edge)
        return await self.go(source,edge)

    async def visit(self, path):
        await self.prepare_tail(path)
        await self.agent.configure_predictors(abtb=True,settle=True)
        if self.installed_path == path:
            # A repeated source is a NEW traversal of an already learned real
            # program, not a replay of an old checkpoint or an elapsed delay.
            return await self.window(path,final_position=self.final_position)
        source = await self.go(self.source,Edge(self.pc,self.program.helper.pcs[0],
            3 if self.final_position == FALLBACK else 1,self.final_position))
        for edge in path.edges()[:5]:
            source = await self.predecessor(source,edge)
        # The final three genuinely learned taken branches, not another
        # synthetic redirect to the anchor, produce its canonical old read.
        result = await self.window(path,final_position=self.final_position)
        self.installed_path = path
        return result

    def snapshot_provider(self, source, position):
        token = self.checker.source_token(source)
        values = self.checker.model.sources.short_snapshot(token).prediction.values()
        return next(((values[f'{way}.provider'],values[f'{way}.counter'],bool(values[f'{way}.predicted']))
            for way in range(4) if values.get(f'{way}.valid') and values.get(f'{way}.hit')
            and values.get(f'{way}.position') == position),None)

    def ahead_counter(self, source, position):
        token = self.checker.source_token(source)
        frame = self.checker.model.sources.snapshot(token).frame
        if frame is None or not frame.valid:return None
        return next((counter for hit,entry,counter in zip(frame.hits,frame.read.entries,frame.counters,strict=True)
                     if hit and entry.position == position and entry.kind == 1),None)

    async def learn_until(self, path, condition, description):
        # A bounded number of real original outcomes, derived from 3-bit
        # direction and 2-bit protection ranges. No delay grants completion.
        for _ in range(2*((7+1)+(3+1))):
            source = await self.visit(path)
            if condition(source):return source
        self.checks.check(True,False,dict(point=description,path=path.ordinal,
            short=self.checker.model.sources.short.state()))

    async def short_guidance(self, *, taken):
        """A different real path steers the base, then Main supplies the outcome."""
        if type(taken) is not bool:raise ValueError('explicit incoming direction required')
        await self.set_main(early=not taken,target=False)
        await self.learn_until(self.program.helper,lambda source:
            self.ahead_counter(source,SHORT_POSITION)==(0 if taken else 3),
            'independent helper establishes an opposed early direction')
        await self.set_main(early=taken,target=False)

    async def short_settle(self):
        await self.pause()
        await self.observation.wait('owned-short-learning-compared',lambda checker:
            checker.model.sources.short.offered is None and checker.model.sources.short.learning is None
            and self.checks.short_pending is None)

    async def short_storage_boundary(self, phase):
        await self.visit(self.program.helper)
        await self.pause()
        indices={identity.index for identity in self.checks.short_identities.values()}
        def complete(checker):
            short=checker.model.sources.short
            dirty=any(version.sequence in short.updates[0].dirty and version.index in indices
                for version in short.updates[0].outstanding)
            return short.offered is None and short.learning is None and self.checks.short_pending is None and not dirty
        await self.observation.wait('owned-short-original-SRAM-services-complete',complete)
        self.checks.check_storage(phase)

    async def seed_short(self):
        self.checks.phase = 'normal-short-history-prerequisites'
        for number,path in enumerate(self.program.short_prerequisites):
            if number:
                await self.set_main(early=True)
                await self.learn_until(self.program.helper_for(path),lambda source:
                    self.ahead_counter(source,SHORT_POSITION) == 3,
                    'other-path actual taken outcomes rebuild the early conditional base')
            await self.set_main(early=False,target=True)
            def qualified(source):
                provider = self.snapshot_provider(source,SHORT_POSITION)
                entry = resident(self.checker.model.sources,(0,path.read_indices[0]))
                useful = self.checker.model.sources.short.useful[0].get(path.read_indices[0],0)
                return (provider is not None and provider[0] == 0 and not provider[2]
                        and entry.valid and entry.tag == path.tags[0] and entry.position == SHORT_POSITION and useful>0)
            source = await self.learn_until(path,qualified,'short prerequisite belongs to its other real branch position')
            self.checks.check(0,self.checks.provider(source,path,SHORT_POSITION)[0],'actual short prerequisite consumer')
        self.checks.reached_phase('protected-short-prerequisites',contexts=len(self.program.short_prerequisites))

    async def negative_base(self, helper, *, require_provider=False):
        self.checks.phase = 'other-history-negative-base'
        await self.set_main(early=False,target=False)
        def qualified(source):
            provider = self.snapshot_provider(source,POSITION)
            return (self.ahead_counter(source,POSITION) == 0
                and self.checker.source_token(source).early.branch.position == FALLBACK
                and (not require_provider or provider is not None and provider[0] == 1 and not provider[2]))
        return await self.learn_until(helper,qualified,
            'helper path establishes a negative early base without overwriting another long history')

    async def positive(self, path, *, require_upper=True):
        await self.negative_base(self.program.helper_for(path))
        await self.set_main(early=False,target=True)
        self.checks.phase = 'positive-long-history-admission-or-reward'
        def qualified(source):
            value = self.snapshot_provider(source,POSITION)
            state = self.checks.ledger.states.get(path.ordinal)
            return (value is not None and value[0] == 1 and value[2] and state is not None
                    and (not require_upper or state.useful == 3))
        source = await self.learn_until(path,qualified,'new long history has a real positive retained consumer')
        self.checks.check((1,True),(self.checks.provider(source,path,POSITION)[0],
                                  self.checks.provider(source,path,POSITION)[2]),'original positive long consumer')
        return source

    async def reverse(self, path):
        await self.negative_base(self.program.helper_for(path))
        expected = self.checks.ledger.reversal(path,taken=False)
        self.checks.declare_result(path,False)
        self.checks.phase = 'selective-real-direction-reversal'
        for state in expected:
            await self.visit(path)
            current = self.checks.ledger.states[path.ordinal]
            self.checks.check((state.counter,state.taken),(current.counter,current.taken),
                              'one declared original NT outcome advances direction independently of global protection')
        source = await self.visit(path)
        self.checks.direction(source,path,taken=False,phase='reversed')
        self.checks.penalized.add(path.ordinal)

    async def read_direction(self, path, *, taken, phase):
        await self.set_main(early=False,target=taken)
        self.checks.phase = 'late-'+phase+'-direction-consumers'
        source = await self.visit(path)
        self.checks.direction(source,path,taken=taken,phase=phase)
        return source

    async def restore(self, path):
        self.checks.declare_result(path,True)
        # Correcting direction can consume the early base's disagreement
        # before the provider becomes reliable again. These are separate
        # semantic obligations: first recover the public T result, then earn
        # protection through fresh, genuinely opposed correct outcomes.
        source = await self.positive(path,require_upper=False)
        # Protection requires fresh correct *opposition*, not repeated correct
        # predictions after the base has learned to agree. Re-establish that
        # semantic prerequisite for every reward. Two passes through the four
        # protection states also allow one independently checked global age.
        for _ in range(2*(3+1)):
            if self.checks.ledger.states[path.ordinal].useful == 3:break
            before = self.checks.ledger.states[path.ordinal]
            ages = self.checks.maintenance.failures.ages
            source = await self.positive(path,require_upper=False)
            if self.checks.maintenance.failures.ages == ages:
                self.checks.check(before.useful+1,self.checks.ledger.states[path.ordinal].useful,
                                  'one new correct opposition restores one logical protection level')
        self.checks.direction(source,path,taken=True,phase='restored')
        self.checks.check(3,self.checks.ledger.states[path.ordinal].useful,
                          'selected path recovers its own protection as well as public direction')
        self.checks.recovered.add(path.ordinal)

    async def observe_maintenance(self):
        maintenance = self.checks.maintenance
        epoch = len(maintenance.receipts)
        if not epoch or epoch in maintenance.consumers:return
        positive = next(path for path in self.program.positives if path.ordinal in self.checks.admitted
            and self.checks.expected_results.get(path.ordinal,True))
        negative = next((path for path in self.program.selected if path.ordinal in self.checks.admitted
            and not self.checks.expected_results.get(path.ordinal,True)),self.program.helper)
        views = {}
        for path,taken in ((positive,True),(negative,False)):
            if path in self.program.helpers:
                source = await self.negative_base(path,require_provider=True)
                self.checks.direction(source,path,taken=False,phase='maintenance')
            else:source = await self.read_direction(path,taken=taken,phase='maintenance')
            views[taken] = dict(self.checks.public_consumers['maintenance'][path.ordinal],history=path.ordinal)
        maintenance.record_consumers(epoch,views)


@asynccontextmanager
async def history_working_set_env(agent, program, coverage,*,checks_factory=HistoryWorkingSetChecks,
                                  binding_factory=history_working_set_binding):
    checks = checks_factory(program,coverage)
    phr = BpuPhrChecker(scope='real predecessor history workset; original index/tag owners',record_limit=8)
    def bind(agent,**options):
        result=binding_factory(agent,**options)
        if isinstance(result,tuple):
            binding,checks.storage_layout=result
            return binding
        return result
    observation = PipelineObservation(agent,checks,sources=EarlyDirectionSources(),binding_factory=bind)
    checks.pipeline = observation.checker
    try:
        async with observation,agent.observe_phr(phr):
            await agent.reset(ANCHOR)
            source = await agent.next_transaction(start_pc=ANCHOR)
            await agent.configure_predictors(ubtb=True,abtb=False,mbtb=True,tage=False,
                sc=False,ittage=False,ras=False,settle=True)
            env = HistoryWorkingSetEnv(agent,observation,source,program,checks)
            await env.pause()
            yield env
            phr.summary()
    except BaseException as error:
        if checks.micro_origins:error.add_note('recent semantic MicroBTB origins: '+repr(tuple(checks.micro_origins)))
        coverage.evidence = dict(checks.summary(),status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    else:coverage.evidence = dict(checks.summary(),status='PASS')
