"""Pure event-driven counterpart; never seeds a DUT or a reference from RTL."""
from dataclasses import replace

from bpuverify.bpu.model.early_direction_sources import EarlyDirectionSources
from bpuverify.bpu.model.pipeline import Outcome
from bpuverify.bpu.model.selection import Kind
from tests.bpu.scoreboard._statistical_joint_program import Program as EventProgram
from tests.bpu.scoreboard.test_semantic_pipeline import boot
from bpuverify.bpu.checker.ahead_working_set import (prefix_main_counts as main_counts,
    prefix_ahead_view as ahead_view,prefix_consumer_matches as qualified)


class PrefixProgram(EventProgram):
    def __init__(self,program):
        self.program=program
        self.a=program.initial_pc
        self.recovery_position=0
        self.model,self.event=boot(EarlyDirectionSources(),pc=self.a)
        self.event=replace(self.event,enabled=(False,False,True,False,False,False,False))
        while self.model.control_pipe[-1]!=self.event.enabled:self.model.advance(replace(self.event,reset=True))
        self.records,self.feedbacks,self.published=[],[],[]
        self.anchor=self.consume(self.a)

    def step(self,event=None):
        cycle=super().step(event)
        if cycle.metadata is not None:self.published.append(cycle.metadata)
        return cycle

    def query(self,pc):
        self.anchor=super().query(self.a)
        index=next((i for i in range(self.program.count) if self.program.pc(i)==pc),None)
        if index is None:return super().query(pc)
        before=len(self.published)
        super().query(self.program.predecessor(index).pc)
        source=next((t for t in self.published[before:] if t.pc==pc),None)
        return source if source is not None else self.consume(pc)

    def resolve_window(self,index,source,early,later):
        choice=self.bank.choose(source,3,self.event.enabled).branch
        return self.feedback(source,*self.program.outcomes(index,choice,early_taken=early,later_taken=later))

    def prepare(self):
        for index in self.program.order:
            edge=self.program.predecessor(index)
            source=self.query(edge.pc)
            self.feedback(source,Outcome(edge.position,edge.target,Kind.DIRECT,True,mispredict=True))
            self.resolve_window(index,self.query(self.program.pc(index)),False,True)
            self.resolve_window(index,self.query(self.program.pc(index)),True,True)
        self.quiet()
        self.event=replace(self.event,enabled=(False,True,True,False,False,False,False))
        while self.model.control_pipe[-1]!=self.event.enabled:self.step(replace(self.event,prediction_ready=False))
        for index in self.program.order:
            # Establish the first Ahead record through real S3 guidance.
            for _ in range(6):
                source=self.query(self.program.pc(index))
                view=ahead_view(self.bank,source)
                if 2 in view and view[2]['counter']==3:break
            else:raise AssertionError('no independently strong original early branch')
            self.establish(index,False,True)
            self.converge(index,(0,3))

    def establish(self,index,early,later):
        for _ in range(9):
            source=self.query(self.program.pc(index))
            counters=main_counts(source)
            if counters.get(2)==(3 if early else 0) and (early or counters.get(12)==(3 if later else 0)):
                return source
            self.resolve_window(index,source,early,later)
        raise AssertionError('declared instruction outcomes did not establish both Main directions')

    def converge(self,index,counts):
        for _ in range(16):
            source=self.query(self.program.pc(index))
            if qualified(self.bank,source,self.program,index,counts):return source
        raise AssertionError(('no full independently qualified prefix consumer',index,counts,
            ahead_view(self.bank,source),source.early))
