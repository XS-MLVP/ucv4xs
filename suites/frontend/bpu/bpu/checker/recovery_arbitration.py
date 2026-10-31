"""Original source and recovery arbitration; no physical coordinate sweep."""
import asyncio
from copy import deepcopy

from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.bpu.coverage.recovery_arbitration import RULES,PROFILES,RecoveryCoverage



class RecoveryChecks:
    def __init__(self,program):
        self.program=program
        self.phase='setup'
        self.pipeline=None
        self.backend=None
        self.frozen={}
        self.pending=[]
        self.completions={}
        self.finalized=False
        self.frame=None
        self.redirect=None
        self.checked_redirect=None
        self.consumer=None
        self.early_gate=self.repair_gate=None
        self.board=Scoreboard('bpu.original-recovery-arbitration')
        self.coverage=RecoveryCoverage(program)
        self.groups=self.coverage.groups

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program,frame=self.frame)))

    def record(self,status,rule,tick):
        if rule not in RULES:raise ValueError('unknown semantic recovery obligation')
        if status=='checked':
            self.completions[rule]=tick
        elif status=='reached':
            self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=dict(tick=tick))
        else:raise ValueError('unknown recovery evidence phase')

    def candidates(self,row,events,cycle,model,phase,previous):
        self.frame=dict(row=deepcopy(row),events=events,cycle=cycle)
        immediate,deferred=[],[]
        if self.phase=='arbitration' and events.redirect is not None:
            self.check(None,self.redirect,'one designated older recovery per lifetime')
            self.check(True,self.backend.history is events.redirect.source,'actual redirect uses its exact old history owner')
            self.check(self.program.target,cycle.next_pc,'backend target wins over current prediction correction')
            self.check(self.program.mode=='collision',bool(cycle.middle_repair),'actual same-cycle collision or serial control')
            self.check(False,bool(cycle.final_repair),'this profile has no third independent late correction')
            if cycle.middle_repair:
                self.check(self.program.pc,cycle.tokens[1].pc,'competing middle correction belongs to the learned early branch')
                self.check((True,False),(cycle.tokens[1].early.branch.taken,cycle.decisions[1].branch.taken),
                           'real micro taken is corrected to cold middle fallthrough')
            self.check(self.program.winning_history,model.lookup_history(events,cycle).history,
                       'lookup history is derived only from original execution source')
            self.redirect=dict(tick=self.pipeline.current_event.tick,target=cycle.next_pc,
                middle_repair=cycle.middle_repair,cancelled=tuple(token.sequence for token in cycle.tokens if token is not None),
                original_sequence=self.backend.sequence,expected_history=self.program.winning_history)
            immediate.append('declared-arbitration-window')
            deferred.extend(('backend-wins','younger-cancelled'))
        return immediate,deferred

    def arm(self):
        self.early_gate=asyncio.get_running_loop().create_future()
        self.repair_gate=asyncio.get_running_loop().create_future()

    def disarm(self):
        for future in (self.early_gate,self.repair_gate):
            if future is not None and not future.done():future.cancel()

    def reached(self,tick,immediate,deferred):
        for rule in (*immediate,*deferred):self.record('reached',rule,tick)

    def checked(self,tick,immediate,deferred):
        cycle=self.frame['cycle']
        if self.early_gate is not None and not self.early_gate.done():
            first=cycle.tokens[0]
            if (first is not None and first.pc==self.program.pc and cycle.fires[1]
                    and cycle.decisions[0].branch.taken and not any(cycle.flushes)):
                # Immutable coherent capture, not a later live checker re-read.
                self.early_gate.set_result((tick,cycle))
        if (self.repair_gate is not None and not self.repair_gate.done() and cycle.middle_repair
                and cycle.tokens[1] is not None and cycle.tokens[1].pc==self.program.pc):
            self.repair_gate.set_result((tick,cycle))
        if self.pending:
            self.check(self.pending[0][0],tick,'arbitration checks use the exact following actual boundary')
            first=cycle.tokens[0]
            self.check(True,first is not None,'the actual following boundary has a new successor')
            self.check(self.program.target,first.pc,'fresh successor is the backend target')
            self.check(self.program.winning_history,first.history.history,'fresh successor owns only restored execution history')
            self.check((None,None),cycle.tokens[1:],'all old middle and late occupancy was cancelled')
            self.check(False,first.sequence in self.redirect['cancelled'],'new successor cannot reuse cancelled identity')
            for _,rule in self.pending:self.record('checked',rule,tick)
            self.checked_redirect=dict(self.redirect,next_tick=tick,new_sequence=first.sequence)
        self.pending=[(tick+2,rule) for rule in deferred]
        for rule in immediate:self.record('checked',rule,tick)

    def own_sources(self,sources):
        for name,source in sources.items():
            self.frozen[name]=(source,deepcopy(source.meta))
            self.check(dict(phrPtr=dict(flag=0,value=0),phrLowBits=0),source.meta.redirect['phr'],
                       'every distinct cold source has reset-derived history, not an actual-state golden seed')
        self.backend=self.pipeline.source_token(sources['backend'])
        self.check(0,self.backend.history.history,'old backend source precedes all speculative path learning')
        self.check(3,len({source.meta_tick for source in sources.values()}),'three actual independent source occurrences')
        for status in ('reached','checked'):self.record(status,'real-old-source',sources['backend'].meta_tick)

    def younger(self,tick,cycle):
        self.check(True,cycle.tokens[0] is not None and cycle.tokens[0].pc==self.program.pc
            and cycle.fires[1] and cycle.decisions[0].branch.taken,'a learned early taken really accepted')
        self.check(False,cycle.tokens[0].history.history==self.backend.history.history,
                   'younger speculative prefix must be distinguishable from the old backend source')
        for status in ('reached','checked'):self.record(status,'distinct-younger-path',tick)

    def consume(self,source):
        self.check(True,self.checked_redirect is not None,'a new public consumer cannot replace missing cancellation proof')
        token=self.pipeline.source_token(source)
        self.check(True,source.prediction_tick>self.redirect['tick'],'consumer is newly accepted after actual redirect')
        self.check((self.program.target,self.program.winning_history),(token.pc,token.history.history),
                   'public consumer independently owns the winning old execution history')
        self.check(self.program.expected_metadata,source.meta.redirect['phr'],'public checkpoint agrees with closed execution expectation')
        self.consumer=dict(prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
                           pc=token.pc,history=token.history.history,metadata=deepcopy(source.meta.redirect['phr']))
        for status in ('reached','checked'):self.record(status,'fresh-history-consumer',source.meta_tick)

    def finish(self):
        self.check(False,self.finalized,'each complete hardware lifetime publishes checked credit once')
        self.check([],self.pending,'no unobserved post-arbitration cancellation remains')
        self.check(0,self.board.status.failed,'earlier mismatch cannot receive final complete credit')
        self.check(True,self.consumer is not None,'a fresh metadata consumer is required')
        for source,frozen in self.frozen.values():self.check(frozen,source.meta,'all original source snapshots remain immutable')
        for status in ('reached','checked'):self.record(status,'immutable-sources',self.consumer['meta_tick'])
        self.check(set(RULES),set(self.completions),'every semantic obligation needs complete original evidence')
        for rule,tick in self.completions.items():
            self.groups['checked'].sample(dict(obligation=self.program.profile+'.'+rule),metadata=dict(tick=tick))
        self.finalized=True
        for group in self.groups.values():self.check(25.0,group.coverage,'this one profile completes its own obligations')

    def summary(self):
        return dict(profile=self.program.profile,redirect=self.checked_redirect,consumer=self.consumer,
            compared=self.board.status.checked,source_ticks={name:value[0].meta_tick for name,value in self.frozen.items()})

    def database(self):return self.coverage.database()
