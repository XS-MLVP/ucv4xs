"""Passive public-SDK service witnesses, never expected-state seeds."""
from bpuverify.common.model.configuration import *
from copy import deepcopy

from toffee import CheckContext, Scoreboard, ScoreboardMode


class MainSiblingChecks:
    alignment,bank = 0,0

    def __init__(self, environment, program):
        self.env,self.program = environment,program
        self.board = Scoreboard('bpu.main-unexecuted-sibling')
        self.held = False
        self.last = None
        self.incoming,self.directions,self.inputs,self.accepted = [],[],[],[]
        self.written = [[] for _ in range(MAIN_WAYS+1)]
        self.snapshots,self.consumers = [],[]
        self.failure = None
        self.status = 'INCOMPLETE'

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(
            self.board.name,ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state(),
                incoming=self.incoming,directions=self.directions,accepted=self.accepted,written=self.written),
            observed_event=self.env.checker.current_event))

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.env.checker.raise_failure()

    def capture_state(self,event,row):
        self.last = event.tick,deepcopy(row)
        if row['training']['valid'] and row['training']['ready']:
            self.inputs.append(event.tick)
        if self.held:
            self.check((1,(0,0,0)),(row['read']['valid'],tuple(port['ready'] for port in row['writes'])),
                       'real prediction read priority, not a forced busy input')
        for owner,port in enumerate(row['incoming']):
            if port['valid']:self.incoming.append(dict(tick=event.tick,owner=owner,bits=deepcopy(port['bits'])))
        if row['direction']['valid']:
            self.directions.append(dict(tick=event.tick,bits=deepcopy(row['direction']['bits'])))

    def write_accepted(self,owner,transfer):
        self.written[owner].append(dict(tick=transfer.accepted_tick,bits=deepcopy(transfer.value)))

    def start(self,source):
        from bpuverify.bpu.model.main_service import STREAM_PC
        token = self.env.checker.source_token(source)
        self.check((STREAM_PC,'micro',STREAM_PC),(token.pc,token.early.source,token.early.branch.target),
                   'normal early self-loop supplies actual read pressure')
        self.held = True

    def summary(self):
        return dict(program=self.program.state(),status=self.status,incoming=self.incoming,
            directions=self.directions,actual_input_ticks=self.inputs,accepted=self.accepted,
            services=self.written,consumers=self.consumers,
            immutable_originals=all(source.meta.resolve==resolve and source.meta.redirect==redirect
                                   for source,resolve,redirect in self.snapshots))
