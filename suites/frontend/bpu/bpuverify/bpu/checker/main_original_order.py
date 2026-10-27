"""Compare passive complete proposals, retained versions and native services."""
from copy import deepcopy
from toffee import Scoreboard,CheckContext,ScoreboardMode
from bpuverify.bpu.model.main_service import observed_counter
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.main_original_order import EARLIER,LATER,INITIAL_TARGET


class Checks:
    def __init__(self,env,program):
        self.env,self.program=env,program
        self.board=Scoreboard('bpu.original-resolution-order')
        self.last=None;self.inputs=[];self.incoming=[];self.directions=[];self.written=[[],[],[]]
        self.failure=None;self.first_error_state=None;self.close_when_retained=None;self.retained_witness=None

    def start(self,sources):
        tokens=tuple(self.env.checker.source_token(source) for source in sources)
        for token in tokens:
            entries=[(s.position,s.kind,s.counter) for row in source_entries(token.lookup) for s in row if s.hit]
            self.check([(EARLIER,3,2),(LATER,1,self.program.sibling_counter)],entries,
                'two normally learned identities and independent not-taken sibling')
            self.check(INITIAL_TARGET,token.middle.branch.target,'each original predicted its actual old target')
        self.check(True,tokens[0].sequence<tokens[1].sequence,'two distinct prediction-age owners')
        return tokens,{}

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
                ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state(),
                    inputs=self.inputs,incoming=self.incoming,directions=self.directions,services=self.written),
                observed_event=self.env.checker.current_event))
        except Exception as error:
            self.failure=error
            row=None if self.last is None else self.last[1]
            self.first_error_state=deepcopy(dict(point=point,
                tick=getattr(self.env.checker.current_event,'tick',None),expected=expected,actual=actual,
                inputs=self.inputs,incoming=self.incoming,directions=self.directions,services=self.written,
                retention=None if row is None else {key:row[key] for key in ('read','writes','dirty','queue')}))
            raise

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.env.checker.raise_failure()

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:self._capture_state(event,row)
        except Exception as error:
            if self.failure is None:self.failure=error
            raise

    def _capture_state(self,event,row):
        self.last=(event.tick,deepcopy(row))
        if row['training']['valid'] and row['training']['ready']:self.inputs.append(event.tick)
        for owner,port in enumerate(row['incoming']):
            if port['valid']:self.incoming.append(dict(tick=event.tick,owner=owner,bits=deepcopy(port['bits'])))
        if row['direction']['valid']:
            self.check(1,row['direction']['ready'],'capacity-safe direction learning cannot be dropped')
            self.directions.append(dict(tick=event.tick,bits=deepcopy(row['direction']['bits'])))
        future=self.close_when_retained
        if future is not None and not future.done() and len(self.incoming)==2:
            owner=self.program.owner;latest=self.program.services[-1]
            port=row['writes'][owner]
            if row['read']['valid'] and port['valid'] and not port['ready'] and port['bits']==latest:
                self.check([[],[],[]],self.written,'both versions are compared before any actual service')
                self.check(1,sum(sum(v) for v in row['dirty']),'one retained latest logical entry, not two old versions')
                direction=row['writes'][2]
                self.check((1,0,self.program.direction),(direction['valid'],direction['ready'],observed_counter(direction['bits'])),
                    'the independently queued direction obligations remain read-blocked')
                self.check(2,len(self.directions),'both actual masked direction proposals exist before release')
                self.retained_witness=dict(tick=event.tick,latest=deepcopy(port['bits']),
                    dirty=sum(sum(v) for v in row['dirty']),read_valid=row['read']['valid'],all_services_blocked=True)
                future.set_result(event)

    def write_accepted(self,owner,transfer):
        self.written[owner].append(dict(tick=transfer.accepted_tick,bits=deepcopy(transfer.value)))

    def entry_services(self):
        return tuple(row['bits'] for row in self.written[self.program.owner])

    def complete(self):
        self.raise_failure()
        return tuple(map(len,self.written))==tuple(len(self.program.services) if i==self.program.owner else 2 if i==2 else 0 for i in range(3))

    def summary(self):
        status=self.board.status
        result=dict(checks=dict(checked=status.checked,passed=status.passed,failed=status.failed),
            input_ticks=self.inputs,incoming=self.incoming,directions=self.directions,
            services=self.written,retained_witness=self.retained_witness)
        if self.first_error_state is not None:result['first_error']=deepcopy(self.first_error_state)
        return result
