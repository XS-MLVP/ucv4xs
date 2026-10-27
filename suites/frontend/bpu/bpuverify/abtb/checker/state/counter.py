"""Compare independent counter state and associate accepted public feedback."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from dataclasses import replace

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.abtb.model.state.counter import CounterReference
from bpuverify.abtb.model.state.counter import TRANSITIONS
from bpuverify.abtb.model.state.counter import coordinates
from bpuverify.abtb.monitor.state.counter import public_transaction


class CounterChecker:
    def __init__(self,*,scope,coverage):
        self.scope,self.coverage=scope,coverage
        self.scoreboard=Scoreboard('abtb.counter_state')
        self.reference=CounterReference()
        self.planned_training=deque()
        self.planned_writes=deque()
        self.pending_transitions=[]
        self.records=[]
        self.confirmed=[]
        self.failure=None
        self.last_tick=None
        self.initialized=False
        self.accepted=0

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def check(self,expected,actual,**request):
        self.raise_failure()
        self.scoreboard.check(expected=expected,actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name,mode=ScoreboardMode.DIRECT,
                request=dict(scope=self.scope,observed_tick=self.last_tick,**request)))

    def plan(self,tx,*,write=None):
        self.raise_failure()
        self.planned_training.append(asdict(tx))
        if write is not None:
            self.planned_writes.append(deepcopy(write))

    def capture(self,observation):
        if self.failure is not None:
            return
        try:
            self.observe(observation)
        except Exception as error:
            self.failure=error

    def observe(self,observation):
        row,event=observation.value,observation.event
        self.records.append(dict(tick=event.tick,**deepcopy(row)))
        context=CheckContext(scoreboard=self.scoreboard.name,mode=ScoreboardMode.DIRECT,
            sequence_id=self.accepted,request=dict(scope=self.scope,
                pending_training=None if not self.planned_training else self.planned_training[0],
                pending1=self.reference.pending1,pending2=self.reference.pending2,
                pending_write=None if not self.planned_writes else self.planned_writes[0]),observed_event=event)
        check=lambda expected,actual:self.scoreboard.check(expected=expected,actual=actual,context=context)
        if self.last_tick is not None:
            check(self.last_tick+2,event.tick)
        self.last_tick=event.tick
        if self.initialized:
            if tuple(self.reference.cells)!=row['cells']:
                cell=next(i for i,(expected,actual) in enumerate(zip(self.reference.cells,row['cells'],strict=True))
                          if expected!=actual)
                bank,s,way=coordinates(cell)
                context=replace(context,request=dict(context.request,
                    first_mismatch=dict(bank=bank,set_index=s,way=way,
                        expected=self.reference.cells[cell],actual=row['cells'][cell])))
            check(tuple(self.reference.cells),row['cells'])
            for transition in self.pending_transitions:
                self.confirmed.append(dict(checked_tick=event.tick,**deepcopy(transition)))
                if transition['transition'] in TRANSITIONS:
                    self.coverage.sample({name:transition[name] for name in ('bank','set_index','way','transition')})
        else:
            check(1,row['reset'])
            self.initialized=True
        accepted=None
        if row['training']['valid']:
            check(True,bool(self.planned_training))
            intended=self.planned_training.popleft()
            check(intended,public_transaction(row['training']['bits']))
            self.accepted+=1
            if row['enable'] and intended['meta']['valid']:
                accepted=intended
        writes=[]
        for bank,port in enumerate(row['writes']):
            if port['valid'] and not row['reset']:
                actual=dict(bank=bank,**{name:port[name] for name in ('set_index','way','reset_counter')})
                check(True,bool(self.planned_writes))
                check(self.planned_writes.popleft(),actual)
                writes.append(actual)
        self.pending_transitions=self.reference.advance(reset=row['reset'],accepted=accepted,writes=writes)

    def summary(self):
        self.raise_failure()
        self.check(0,len(self.planned_training),phase='all-public-pulses-observed-once')
        self.check(0,len(self.planned_writes),phase='all-independent-allocation-writes-observed-once')
        return dict(cycles=len(self.records),accepted_public_feedback=self.accepted,
            physical_cell_comparisons=max(0,len(self.records)-1)*1024,
            confirmed_transitions=len(self.confirmed),checks=asdict(self.scoreboard.status))
