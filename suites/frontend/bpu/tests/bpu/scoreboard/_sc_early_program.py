"""Synthetic actuals qualify checkers only; all predictors start from reset."""
from dataclasses import replace
from types import SimpleNamespace as NS

from toffee import Scoreboard,XEvent,XEventKind,XPhase

from bpuverify.bpu.checker.sc_early_learning import Checks
from bpuverify.bpu.model.pipeline import Redirect,Resolution,Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.statistical_joint_sources import StatisticalJointSources
from bpuverify.tage.model.semantic import TABLES
from tests.bpu.scoreboard._conditional_prefix_program import Program as Foundation
from tests.bpu.scoreboard.test_early_direction_checking import actual_live,actual_fast
from bpuverify.bpu.checker.early_direction import live_values,fast_values


class Program(Foundation):
    def __init__(self,profile):
        entry,mode = profile.split('.')
        super().__init__(entry+'.weak-alternate.'+mode,sources_factory=StatisticalJointSources)
        self.checks = Checks(profile)
        self.receipts,self.acceptances = {},{}
        self.mutate = None
        self.notification_phase = XPhase.RISING_STABLE
        self.checks.pipeline = NS(model=self.model,board=Scoreboard('pure-SC-early-lifetime'),
            raise_failure=lambda:None,source_token=lambda source:source.token,last_tick=None)

    @property
    def bank(self):
        return self.model.sources

    def receipt(self,token):
        return self.receipts[token.sequence]

    def step(self,event=None):
        event = self.event if event is None else event
        c = self.checks
        if event.feedback is not None:
            request = event.feedback
            is_sc = request.pc==self.pc+0x400 and self.model.control_pipe[-1][4]
            name = f'SC-negative-experience-{len(c.accepted_SC_inputs)}' if is_sc else f'preparation-{len(c.plans)}'
            c.plan(name,self.receipt(request.origin),tuple(b for b in request.branches if b is not None))
        cycle = self.model.evaluate(event)
        self.tick += 2
        c.pipeline.current_event = XEvent(event_id=self.tick,tick=self.tick,phase=self.notification_phase,
            kind=XEventKind.CLOCK_RISE)
        actual = actual_live(self.bank,cycle.enabled[1])
        if self.mutate is not None:
            self.mutate(actual)
        result = c.candidates(dict(observed=dict(early_direction=actual)),event,cycle,self.model,'synthetic',None)
        assert result == (), 'empty obligations still require reached/checked callbacks'
        expected,observed = live_values(self.bank,cycle.enabled[1],actual)
        c.pipeline.board.check(expected=expected,actual=observed)
        expected,observed = fast_values(self.bank,cycle,actual_fast(self.bank,cycle))
        c.pipeline.board.check(expected=expected,actual=observed)
        self.model.advance(event)
        c.checked(self.tick)
        c.pipeline.last_tick = self.tick
        if cycle.fires[1] and not cycle.flushes[0]:
            self.acceptances[cycle.tokens[0].sequence] = self.tick
        if cycle.metadata is not None and event.redirect is None:
            token = cycle.metadata
            self.receipts[token.sequence] = NS(token=token,prediction_tick=self.acceptances[token.sequence],
                meta_tick=self.tick,meta=dict(owner=token.sequence))
        if cycle.final_repair:
            self.repairs.append((self.tick,cycle))
        return cycle

    def restart(self):
        self.quiet()
        self.step(replace(self.event,redirect=Redirect(self.anchor.history,self.a//8*8+4,self.pc,True,Kind.DIRECT)))

    def query_pc(self,pc):
        self.quiet()
        self.step(replace(self.event,redirect=Redirect(self.anchor.history,self.a//8*8+4,pc,True,Kind.DIRECT)))
        return self.source(pc=pc)

    def configure_sc(self,enabled):
        self.quiet()
        values = list(self.event.enabled)
        values[4] = enabled
        self.event = replace(self.event,enabled=tuple(values))
        while self.model.control_pipe[-1]!=self.event.enabled:
            self.step(replace(self.event,prediction_ready=False))
        self.quiet()

    def teaching_outcome(self,source,*,taken,maximum=False):
        idle = self.quiet()
        late = self.bank.statistical_snapshot(source,resolved=True).late.branch
        wrong = late.position!=2 if taken else late.position==2
        branches = (Outcome(2,self.condition_target,Kind.CONDITIONAL,taken,mispredict=wrong),)
        if not taken:
            branches += (Outcome(4,self.a,Kind.DIRECT,True),)
        request = Resolution(source.history,source.pc,branches,origin=source)
        if maximum:
            feedback = self.bank.feedback_for(request)
            for _ in range(128):
                candidate = self.bank.tage.allocation_at_next_accept(feedback)
                if candidate is not None and candidate[0]==TABLES-1:
                    break
                self.step(idle)
            else:
                raise AssertionError('highest-history semantic allocation opportunity missing')
        self.step(replace(idle,feedback=request))
        self.quiet()

    async def complete(self):
        detail = super().prepare_sources()
        c = self.checks
        c.seed,c.stable = self.receipt(self.seed),self.receipt(self.anchor)
        c.target_control = self.receipt(self.model.published[detail['target_original']])
        for source in (c.seed,c.stable,c.target_control):
            c.save(source)
        self.conditional(self.query())
        self.configure(tage=True)
        self.conditional(self.query(),wrong=True)
        assert self.direction_ready(self.query())
        self.teaching_outcome(self.query_pc(self.pc+0x400),taken=True)
        self.teaching_outcome(self.query_pc(self.pc+0x400),taken=False,maximum=True)
        self.configure_sc(True)
        originals = tuple(self.query_pc(self.pc+0x400) for _ in range(4))
        for source in originals:
            self.teaching_outcome(source,taken=False)
        c.sc_control = self.receipt(self.query())
        c.save(c.sc_control)
        self.configure(early=True)
        c.open()
        self.restart()
        for _ in range(256):
            self.step(self.event if self.flowing or c.selected is None else replace(self.event,prediction_ready=False))
            if c.SC_witness is not None:
                break
        else:
            raise AssertionError('no genuine original SC teacher')
        teacher = self.model.published[c.repair['owner']]
        c.save(self.receipt(teacher))
        self.quiet()
        for _ in range(256):
            if c.new_a is not None and c.new_b is not None:
                break
            self.step()
        else:
            raise AssertionError('natural new early consumer not published')
        for record in (c.new_a,c.new_b):
            c.save(self.receipt(self.model.published[record['owner']]))
        self.quiet()
        for _ in range(16):
            if c.consumer_confirmed is not None:
                return
            self.step(replace(self.event,prediction_ready=False))
        raise AssertionError('newer consumer feedback has no exact actual-state confirmation')
