"""Owned program lifetimes plus read-only resource observations.

This is deliberate omission of call retirement notifications, not a claim of
normal FTQ legality. Actual pointers never initialize or repair the reference.
"""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode
from bpuverify.bpu.checker.ras.semantic import RasSemanticComponentChecker
from bpuverify.bpu.coverage.ras_neutral_gap import RULES
from bpuverify.bpu.model.ras.capacity import CAPACITY,OLD_CALL,NEW_CALL,NEW_RETURN,call_address
from bpuverify.bpu.model.ras.neutral_gap import HOLD_DISTANCE,NEUTRAL


class RasNeutralGapChecks(RasSemanticComponentChecker):
    def __init__(self,coverage):
        super().__init__()
        self.lifecycle=coverage
        self._reset_scope()

    def _reset_scope(self):
        self.reached=set();self.closed=False;self.resources=[];self.restores=[];self.retirements=[]
        self.originals=();self.frozen=();self.reused_count=0

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
            sequence_id=self.input_tick,request=dict(point=point,state=self.model.state())))
        except Exception as error:self.failure=error;raise

    def mark(self,index):
        self.lifecycle.record('reached',RULES[index],self.last_actual[2]);self.reached.add(index)

    def capture_input(self,event,events,*,consumer):
        retired=self.model.retirements
        super().capture_input(event,events,consumer=consumer)
        if events.reset:self._reset_scope();return
        if self.failure is not None:return
        if self.model.last_applied is not None and self.model.last_applied[0]=='recovery':self.restores.append(event.tick)
        if self.model.retirements>retired:self.retirements.append(event.tick)

    def capture_output(self,event,actual,*,retained=None,consumer=None,resources=None):
        super().capture_output(event,actual,retained=retained,consumer=consumer)
        if self.failure is not None or not self.initialized:return
        try:
            if resources is None:raise AssertionError('neutral-gap verification requires read-only BOS and guard observations')
            wanted=dict(bos=self.model.retired_calls%32,guarded=int(self.model.guarded))
            observed=dict(bos=16*resources['bos']['flag']+resources['bos']['value'],guarded=resources['guarded'])
            self.check(wanted,observed,'owned lifetime credit and registered capacity guard')
            self.resources.append(dict(tick=event.tick,**observed))
        except Exception as error:self.failure=error

    def unchanged_committed(self):
        self.check((0,tuple((0,0) for _ in range(8))),
            (self.model.committed_head,tuple((f.address,f.repeat) for f in self.model.committed)),
            'neutral notifications never fabricate a committed call, return or address')

    def filled(self,sources,*,start=0):
        programs=tuple(self.owned_program(source) for source in sources)
        self.check((OLD_CALL,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'genuine old call instruction sources')
        self.check(True,len(sources)>=CAPACITY-start+2,'real extra guarded offers required')
        self.check(tuple(range(start,CAPACITY))+(CAPACITY,)*(len(sources)-(CAPACITY-start)),
            tuple(p.calls for p in programs),'accepted old versions versus genuinely guarded offers')
        self.check((CAPACITY,True,0),(self.model.program.calls,self.model.guarded,self.model.retired_calls),
            'omitted notifications exhaust capacity without retiring call data')
        self.unchanged_committed()
        self.originals+=tuple(sources);self.frozen+=tuple(deepcopy(s.meta.redirect['ras']) for s in sources)
        self.mark(0)

    def neutral(self,sources,*,calls):
        self.check(True,bool(sources),'at least one real neutral S3 source required')
        self.check((NEUTRAL,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'neutral is an actual different direct instruction')
        for source in sources:self.check(calls,self.owned_program(source).calls,'neutral source names the independently owned prefix')
        self.check((calls,calls==CAPACITY),(self.model.program.calls,self.model.guarded),'neutral source cannot create or remove a call')
        self.mark(1 if calls==HOLD_DISTANCE else 3)

    def held(self):
        self.check((1,0,False,None),(self.model.retirements,self.model.retired_calls,self.model.guarded,self.model.pending_retirement),
            'distance exactly two holds lifetime credit after actual registered comparison')
        self.check(dict(bos=0,guarded=0),{k:self.resources[-1][k] for k in ('bos','guarded')},'actual distance-two hold')
        self.unchanged_committed();self.mark(2)

    def reclaimed(self):
        self.check((2,CAPACITY-1,False,None),
            (self.model.retirements,self.model.retired_calls,self.model.guarded,self.model.pending_retirement),
            'large neutral gap releases all but the newest live version')
        self.check(2,len(self.retirements),'both neutral retirement effects actually crossed the registered boundary')
        effect=self.retirements[-1]
        rows=[row for row in self.resources if row['tick']>=effect+1]
        self.check(True,bool(rows) and rows[0]['bos']==CAPACITY-1 and rows[0]['guarded']==1,
            'registered credit effect precedes guard release')
        self.check(True,any(row['bos']==CAPACITY-1 and row['guarded']==0 for row in rows),'actual guard subsequently releases')
        self.check([], [tick for tick in self.restores if tick>=effect], 'release is not caused by a later recovery')
        self.check(call_address(OLD_CALL),self.model.program.head.address,'newest old call remains owned after reclamation')
        self.unchanged_committed();self.mark(4);self.mark(5)

    def reused(self,sources):
        self.check(True,len(sources)>=6,'real new call versions required')
        self.check((NEW_CALL,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'actual new call identity')
        programs=tuple(self.owned_program(source) for source in sources)
        self.check(tuple(range(CAPACITY,CAPACITY+len(sources))),tuple(p.calls for p in programs),'new versions reuse reclaimed storage across wrap')
        self.check((CAPACITY-1,False,call_address(NEW_CALL)),
            (self.model.retired_calls,self.model.guarded,self.model.program.head.address),'reclaimed credit permits fresh new-address calls')
        self.unchanged_committed();self.reused_count=len(sources);self.mark(6)

    def returned(self,sources):
        self.check(True,0<len(sources)<self.reused_count-1,'fresh returns leave a live new frame after younger cancellation')
        self.check((NEW_RETURN,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'actual fresh return consumer instruction')
        for source in sources:self.check(call_address(NEW_CALL),self.owned_program(source).head.address,'fresh return uses new owned frame')
        self.check((2,CAPACITY-1,False,call_address(NEW_CALL)),
            (self.model.retirements,self.model.retired_calls,self.model.guarded,self.model.program.head.address),
            'no phantom retirement while new frames are consumed')
        self.check(self.frozen,tuple(s.meta.redirect['ras'] for s in self.originals),'all original metadata remains immutable')
        self.unchanged_committed();self.mark(7)

    def finish(self):
        self.raise_failure()
        if self.closed:return
        super().finish()
        self.check(set(range(len(RULES))),self.reached,'all neutral lifetime obligations must close')
        self.check(None,self.model.pending_retirement,'no unchecked registered notification')
        for rule in RULES:self.lifecycle.record('checked',rule,self.last_actual[2])
        self.lifecycle.finish();self.closed=True

