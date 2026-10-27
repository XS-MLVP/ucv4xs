"""Real semantic learning program for pure qualification, never a DUT oracle seed."""
from bpuverify.common.model.configuration import TAGE_ALLOCATION_WAIT
from dataclasses import replace

from bpuverify.bpu.model.pipeline import Outcome, Redirect, Resolution
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.statistical_joint_sources import StatisticalJointSources
from bpuverify.tage.model.semantic import TABLES
from tests.bpu.scoreboard.test_semantic_pipeline import boot


class Program:
    def __init__(self, *, positive, pc=0x40000002, early=False,anchor_pc=0x40000103,recovery_position=4,sources=None):
        self.a, self.b, self.x = anchor_pc, pc, pc + 0x10000
        self.recovery_position=recovery_position
        self.d = self.a + 0x100
        self.positive = positive
        self.model, self.event = boot(StatisticalJointSources() if sources is None else sources, pc=self.a)
        self.event = replace(self.event, enabled=(False, early, True, False, False, True, False))
        while self.model.control_pipe[-1] != self.event.enabled:
            self.model.advance(replace(self.event, reset=True))
        self.records, self.feedbacks = [], []
        self.anchor = self.consume(self.a)

    @property
    def bank(self):
        return self.model.sources

    def step(self, event=None):
        cycle = self.model.advance(self.event if event is None else event)
        self.records.append(cycle)
        return cycle

    def quiet(self):
        idle = replace(self.event, prediction_ready=False)
        for _ in range(256):
            self.step(idle)
            if self.model.stages[1:] == (None, None) and not self.bank.main_pending():
                return idle
        raise AssertionError('owned predictor learning did not drain')

    def consume(self, pc):
        for _ in range(128):
            token = self.step().metadata
            if token is not None and token.pc == pc and token.lookup is not None:
                self.quiet()
                return token
        raise AssertionError('no real published original for the declared program PC')

    def query(self, pc):
        idle = self.quiet()
        self.step(replace(idle, redirect=Redirect(self.anchor.history, (self.a // 16) * 16 + self.recovery_position,
            pc, True, Kind.INDIRECT)))
        return self.consume(pc)

    def controls(self, *, tage=None, sc=None, target=None, micro=None):
        self.quiet()
        enabled = list(self.event.enabled)
        for index, value in ((0, micro), (3, tage), (4, sc), (5, target)):
            if value is not None:
                enabled[index] = value
        self.event = replace(self.event, enabled=tuple(enabled))
        for _ in range(3):
            self.step(replace(self.event, prediction_ready=False))
        self.quiet()

    def feedback(self, source, *branches, maximum=False):
        idle = self.quiet()
        request = Resolution(source.history, source.pc, tuple(branches), origin=source)
        if maximum:
            transaction = self.bank.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                candidate = self.bank.tage.allocation_at_next_accept(transaction)
                if candidate is not None and candidate[0] == TABLES - 1:
                    break
                self.step(idle)
            else:
                raise AssertionError('no highest-history semantic allocation opportunity')
        self.step(replace(idle, feedback=request))
        self.feedbacks.append(request)
        self.quiet()
        return request

    def conditional(self, source, taken, *, maximum=False):
        late = self.bank.statistical_snapshot(source, resolved=True).late.branch
        wrong = (late.position != 2 or not late.taken or late.kind != Kind.CONDITIONAL
                 or late.target != self.d) if taken else late.taken and late.position == 2
        branches = (Outcome(2, self.d, Kind.CONDITIONAL, taken, mispredict=bool(wrong)),)
        if not taken:
            kind = Kind.INDIRECT if source.pc == self.b else Kind.DIRECT
            tail_wrong = not wrong and (late.position, late.target, late.kind, late.taken) != (4, self.a, kind, True)
            branches += (Outcome(4, self.a, kind, True, mispredict=tail_wrong),)
        return self.feedback(source, *branches, maximum=maximum)

    def prepare_branch(self, pc, *, target_branch):
        self.controls(tage=False)
        if target_branch:
            # A real indirect target is learned before the earlier condition.
            source = self.query(pc)
            self.feedback(source, Outcome(4, self.a, Kind.INDIRECT, True, mispredict=True))
            for _ in range(2):
                source = self.query(pc)
                self.feedback(source, Outcome(4, self.a, Kind.INDIRECT, True))
        self.conditional(self.query(pc), True)
        self.conditional(self.query(pc), False)
        if not self.positive:
            self.conditional(self.query(pc), True)
        self.controls(tage=True)
        self.conditional(self.query(pc), self.positive, maximum=True)
        if target_branch:
            self.controls(tage=False)
            self.conditional(self.query(pc), not self.positive)
            self.controls(tage=True)
        source = self.query(pc)
        values = dict(self.bank.tage_snapshot(source, resolved=True).wanted)
        main = source.lookup.values()
        slot, = [slot for slot in range(10) if main.get(f'{slot}.valid') and main[f'{slot}.position'] == 2]
        assert values[f'{slot}.table'] == TABLES - 1
        assert values[f'{slot}.counter'] == (4 if self.positive else 3)
        direction = values[f'{slot}.taken'] if values[f'{slot}.valid'] else main[f'{slot}.taken']
        assert bool(direction) is (not self.positive if target_branch else self.positive)
        return source, slot

    def prepare(self):
        self.prepare_branch(self.b, target_branch=True)
        self.prepare_branch(self.x, target_branch=False)
        self.controls(sc=True)
        target = self.query(self.b)
        original = self.bank.statistical_snapshot(target, resolved=True)
        sources = tuple(self.query(self.x) for _ in range(3 if self.positive else 4))
        # Two instruction identities share semantic SC features, not TAGE
        # identity. The target branch itself is never trained in this phase.
        for source in sources:
            teaching = self.bank.statistical_snapshot(source, resolved=True)
            assert teaching.prediction.read.indices == original.prediction.read.indices
            assert teaching.original.history.common_valid is False
            self.conditional(source, self.positive)
        fresh = self.query(self.b)
        return target, original, sources, fresh


class ContextProgram(Program):
    """Same genuine prefix and feedback plan as the DUT context program."""
    def __init__(self,profile,*,layout_type=None):
        from bpuverify.bpu.model.statistical_prefix import ContextLayout
        self.layout=(layout_type or ContextLayout)(profile)
        super().__init__(positive=True,pc=self.layout.b,anchor_pc=self.layout.a,
            recovery_position=self.layout.a%16+self.layout.recovery_offset)
        self.d=self.layout.d

    def query(self,pc):
        if pc!=self.b:
            return super().query(pc)
        super().query(self.layout.prefix)
        return self.consume(pc)

    def conditional(self,source,taken,*,maximum=False):
        late=self.bank.statistical_snapshot(source,resolved=True).late
        return self.feedback(source,self.layout.outcome(source,late,taken),maximum=maximum)

    def probe_invalid_history(self,source):
        from bpuverify.bpu.model.selection import fallthrough
        stride=fallthrough(self.layout.jump).branch.target-self.layout.jump
        entry=self.layout.jump-stride*(len(self.model.stages)+1)
        before=self.bank.statistical_snapshot(source).read
        self.step(replace(self.quiet(),redirect=Redirect(source.history,source.pc,entry,True,Kind.INDIRECT)))
        for _ in range(16*(len(self.model.stages)+1)):
            cycle=self.step();first=cycle.tokens[0]
            if (first is not None and first.pc==self.layout.jump and cycle.fires[1] and not cycle.flushes[0]):
                assert not cycle.decisions[0].branch.taken
                break
        else:raise AssertionError('normal program did not issue the original warm context')
        self.quiet()
        token=self.model.stages[0]
        read=self.bank.statistical_snapshot(token).read
        assert token.pc==source.pc and read.context.common_valid
        assert read.indices[2:6]==before.indices[2:6] and all(any(row) for row in read.weights[2:6])
        assert self.model.stages[0] is token
        self.controls(sc=False)
        self.anchor=Program.query(self,self.a)
        self.controls(sc=True)
        self.anchor=Program.query(self,self.a)
        assert not self.bank.statistical_snapshot(self.anchor).read.context.common_valid
        return token,self.anchor

    def setup(self):
        p=self.layout
        self.controls(target=False)
        for pc,position,target,kind in ((p.prefix,2,p.prefix_target,Kind.CONDITIONAL),
                (p.jump,0,p.b,Kind.DIRECT)):
            source=super().query(pc)
            self.feedback(source,Outcome(position,target,kind,True,mispredict=True))
        self.conditional(self.query(p.b),True)
        self.controls(tage=True)
        self.conditional(self.query(p.b),False,maximum=True)
        for _ in range(2 if p.agrees else 1):
            self.conditional(self.query(p.b),p.agrees)
        self.controls(sc=True)
        control=self.query(p.b)
        originals=tuple(self.query(p.b) for _ in range(4))
        self.controls(tage=False)
        for source in originals:
            self.conditional(source,True)
        self.controls(tage=True)
        fresh=self.query(p.b)
        return control,originals,fresh


class ContextBurstProgram(ContextProgram):
    def __init__(self,profile):
        from bpuverify.bpu.model.sc_admission import ContextBurstLayout
        super().__init__(profile,layout_type=ContextBurstLayout)

    def query(self,pc):
        if pc==self.b:raise ValueError('an explicit incoming context is required')
        if pc!=self.a:self.anchor=Program.query(self,self.a)
        return Program.query(self,pc)

    def query_context(self,context):
        if not self.event.enabled[4]:self.controls(sc=True)
        self.anchor=Program.query(self,self.a)
        start=len(self.records)
        first=Program.query(self,self.layout.prefix_for(context))
        from bpuverify.bpu.model.common_history import GHR_WIDTH
        source=None
        for _ in range(GHR_WIDTH+len(self.model.stages)+1):
            # Include sources published while quiet() drained younger work.
            candidates={c.metadata.sequence:c.metadata for c in self.records[start:] if c.metadata is not None
                and c.metadata.pc==self.layout.loop_prefix and c.metadata.sequence>=first.sequence}
            for token in sorted(candidates.values(),key=lambda t:t.sequence):
                value=self.bank.queries.snapshot(token).metadata
                if value.valid and (value.ghr,value.bw)==(self.layout.exit_history(context),)*2:
                    source=token;break
            if source is not None:break
            self.consume(self.layout.loop_prefix)
        if source is None:raise AssertionError('no independently owned loop experience')
        self.step(replace(self.quiet(),redirect=Redirect(source.history,self.layout.loop_prefix+2,
            self.layout.loop_prefix+32,False,Kind.CONDITIONAL)))
        return self.consume(self.b)

    def conditional(self,source,taken,*,maximum=False,learn_sc=False):
        if not learn_sc:self.controls(sc=False)
        result=super().conditional(source,taken,maximum=maximum)
        if not learn_sc:self.controls(sc=True)
        return result

    def sc_feedback(self,source,taken):
        self.controls(tage=False)
        result=self.conditional(source,taken,learn_sc=True)
        self.controls(tage=True)
        return result

    def provider(self,source):
        value=self.bank.statistical_snapshot(source,resolved=True)
        slot,=[i for i,b in enumerate(value.branches) if b is not None and b.position==self.layout.position]
        fields=dict(self.bank.tage_snapshot(source,resolved=True).wanted)
        return slot,fields,value

    def setup(self):
        p=self.layout
        self.controls(target=False)
        self.controls(micro=True)
        self.feedback(self.query(p.loop),Outcome(4,p.loop,Kind.DIRECT,True,mispredict=True))
        self.controls(micro=False)
        self.feedback(self.query(p.loop_prefix),Outcome(2,p.loop_prefix,Kind.CONDITIONAL,True,mispredict=True))
        self.feedback(self.query(p.jump),Outcome(0,p.b,Kind.DIRECT,True,mispredict=True))
        for context in p.contexts:
            self.controls(tage=False)
            for _ in range(3):self.conditional(self.query_context(context),True)
            self.controls(tage=True)
            source=self.query_context(context)
            slot,fields,_=self.provider(source)
            if not fields[f'{slot}.has_provider']:self.conditional(source,False,maximum=True)
            for _ in range(8):
                source=self.query_context(context)
                slot,fields,_=self.provider(source)
                counter=fields[f'{slot}.counter']
                if counter==p.provider_counter:break
                self.conditional(source,counter<p.provider_counter)
            else:raise AssertionError('no declared TAGE original')
        self.controls(sc=True)
        teachers=tuple(self.query_context(context) for context in p.teaching_contexts)
        assert all(not self.provider(t)[2].prediction.used[self.provider(t)[0]] for t in teachers)
        for source in teachers:self.sc_feedback(source,True)
        originals=tuple(self.query_context(context) for context in p.capture_contexts)
        for source in originals:
            slot,_,value=self.provider(source)
            assert (value.prediction.used[slot],value.prediction.above[slot],value.prediction.directions[slot])==(1,1,1)
        for source in originals[:p.weakening_count]:self.sc_feedback(source,False)
        controls=tuple(self.query_context(context) for context in p.contexts)
        for source in controls:
            slot,_,value=self.provider(source)
            assert not value.prediction.used[slot] and not value.prediction.above[slot]
        return tuple(originals[i] for i in p.arrival_order),controls

    def return_from_stream(self):
        from bpuverify.bpu.model.early_aging import require_recovery_window
        from bpuverify.bpu.model.path_history import WIDTH,LAYOUT,SHIFT
        self.quiet()
        recent=max((t for t in self.model.published.values() if t.pc==self.layout.loop),key=lambda t:t.sequence)
        width=max(length for length,_ in LAYOUT)
        require_recovery_window(self.model.history.taken_edges,recent.history.taken_edges,
            capacity=WIDTH,history_bits=width,shift=SHIFT)
        self.step(replace(self.quiet(),prediction_ready=False,
            redirect=Redirect(recent.history,recent.pc,self.a,True,Kind.INDIRECT)))
        root=self.consume(self.a)
        for _ in range((width+SHIFT-1)//SHIFT+len(self.model.stages)+1):
            if root.history.history%(1<<width)==0:break
            self.step(replace(self.quiet(),redirect=Redirect(root.history,self.a,self.a,True,Kind.DIRECT)))
            root=self.consume(self.a)
        else:raise AssertionError('no independently owned zero-feature root')
        self.controls(tage=True,micro=False)
        self.anchor=root
        self.anchor=Program.query(self,self.a)
        assert self.anchor.history.history%(1<<width)==0
