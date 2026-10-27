"""The independent persistent program owns frames, versions and retirement."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode
from bpuverify.bpu.checker.ras.semantic import RasSemanticComponentChecker
from bpuverify.bpu.coverage.ras_reuse import RULES
from bpuverify.bpu.model.ras.capacity import CAPACITY,PRESERVED,OLD_CALL,OLD_RETURN,NEW_CALL,NEW_RETURN,call_address


class RasReuseChecks(RasSemanticComponentChecker):
    def __init__(self,coverage):
        super().__init__()
        self.lifecycle=coverage;self.reached=set();self.closed=False
        self.calls=[];self.blocked_calls=[];self.blocked_returns=[];self.restores=[];self.ignored=[]
        self.originals=();self.frozen=();self.protected=None;self.restored=None;self.kept_new=()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
            sequence_id=self.input_tick,request=dict(point=point,program=self.model.program,
                retired_calls=self.model.retired_calls,guarded=self.model.guarded,restores=len(self.restores))))
        except Exception as error:self.failure=error;raise

    def mark(self,index,tick):self.lifecycle.record('reached',RULES[index],tick);self.reached.add(index)

    def capture_input(self,event,events,*,consumer):
        before=self.model.program;guarded=self.model.guarded;pending=self.model.pending_recovery
        super().capture_input(event,events,consumer=consumer)
        if events.reset:
            self.calls.clear();self.blocked_calls.clear();self.blocked_returns.clear();self.restores.clear();self.ignored.clear()
            self.originals=self.frozen=self.kept_new=();self.protected=self.restored=None
            self.reached.clear();self.closed=False
            return
        if self.failure is not None or not self.initialized or not events.enabled or events.reset:return
        if self.model.last_applied is not None and self.model.last_applied[0]=='speculation' and events.action==2:
            self.calls.append((event.tick,before,events.address))
        elif guarded and events.action==2 and self.model.last_applied is None:self.blocked_calls.append(event.tick)
        elif guarded and events.action==1 and self.model.last_applied is None:self.blocked_returns.append(event.tick)
        if pending is not None:
            if self.model.last_applied is not None and self.model.last_applied[0]=='recovery':
                self.restores.append((event.tick,before,self.model.program,guarded))
            elif guarded:self.ignored.append((event.tick,before,self.model.program))

    def filled(self,sources):
        programs=tuple(self.owned_program(s) for s in sources)
        self.check((OLD_CALL,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'actual originals all belong to the declared old call site')
        self.check(True,len(sources)>=CAPACITY+2,'both true full capacity and extra real offers required')
        self.check(tuple(range(CAPACITY))+(CAPACITY,)*(len(sources)-CAPACITY),tuple(p.calls for p in programs),
            'original source counts identify accepted versus guarded call offers')
        self.check((CAPACITY,True),(self.model.program.calls,self.model.guarded),'queue guard reached from owned calls')
        self.check(CAPACITY,len(self.calls),'exactly capacity accepted call versions, never all public offers')
        self.check(2,self.calls[-1][0]-self.calls[-2][0],'real adjacent final calls fill the registered guard margin')
        self.check(True,len(self.blocked_calls)>=2,'actual guarded call offers were observed')
        self.check(True,all(p.head.address==call_address(OLD_CALL) for p in programs[1:]),'all original calls belong to the old identity')
        self.originals=tuple(sources);self.frozen=tuple(deepcopy(s.meta.redirect['ras']) for s in sources)
        self.mark(0,sources[-1].meta_tick);self.mark(1,sources[-1].meta_tick)

    def guarded_returns(self,sources):
        self.check(True,len(sources)>=2 and len(self.blocked_returns)>=2,'real guarded return offers required')
        self.check((OLD_RETURN,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'guarded offers belong to the actual old return instruction')
        for s in sources:self.check(CAPACITY,self.owned_program(s).calls,'guarded returns cannot alter the original prefix')
        self.check(True,bool(self.ignored),'same-current source restore was really rejected under guard')
        self.check(True,all(a==b for _,a,b in self.ignored),'rejected recovery must not change the persistent program')
        self.check((CAPACITY,True),(self.model.program.calls,self.model.guarded),'guarded call/return/current restore leave state unchanged')
        self.mark(2,sources[-1].meta_tick)

    def recovered(self,source,program):
        self.check(PRESERVED,program.calls,'older checkpoint has real reclaimable capacity')
        self.check(True,any(before.calls==CAPACITY and after==program and guarded
            for _,before,after,guarded in self.restores),'actual registered older recovery, not an assigned model state')
        self.check((program,False),(self.model.program,self.model.guarded),'post-restore program and released guard compared')
        self.restored=source;self.mark(3,self.last_actual[2])

    def old_retired(self,sources,returns):
        self.check(PRESERVED,len(sources),'only surviving old calls retire')
        self.check(True,bool(returns),'at least one real old return survives younger rollback')
        self.check(PRESERVED+len(returns),self.model.retirements,'all surviving old operations retire once')
        self.check(call_address(OLD_CALL),self.model.program.head.address,'old live prefix still owns its return address')
        self.protected=tuple(self.model.committed)
        self.mark(4,self.last_actual[2])

    def reused(self,sources):
        programs=tuple(self.owned_program(s) for s in sources)
        self.check((NEW_CALL,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'actual new sources belong to a different call identity')
        new=[p for _,p,address in self.calls if address==call_address(NEW_CALL)]
        self.check(True,len(new)>=6 and len(sources)>=6,'new identity has real accepted versions before reuse credit')
        self.check(tuple(range(PRESERVED,PRESERVED+len(sources))),tuple(p.calls for p in programs),
            'new sources are independently owned chronological versions')
        self.check(True,any(p.calls>=CAPACITY for p in new),'new versions cross the bounded-storage wrap')
        self.check(True,self.model.retired_calls>0,'reclaimed old versions, not live entries, are reused')
        self.check(call_address(NEW_CALL),self.model.program.head.address,'new address must not resurrect the old return target')
        self.mark(5,sources[-1].meta_tick)

    def new_retired(self,sources,cancelled):
        self.check(True,len(sources)>=5,'kept new prefix is nonempty after younger call cancellation')
        self.check(PRESERVED+len(sources),self.model.program.calls,'only the younger new call is undone')
        self.check(True,cancelled.meta_tick>sources[-1].meta_tick,'cancelled source is younger than all new retirements')
        for index,expected in enumerate(self.protected):
            if expected.address==call_address(OLD_CALL):self.check(expected,self.model.committed[index],'old retained groups survive new-address reuse')
        self.kept_new=tuple(sources);self.mark(6,self.last_actual[2])

    def final_returns(self,sources):
        self.check(True,0<len(sources)<len(self.kept_new),'fresh returns leave a surviving new-address frame')
        self.check((NEW_RETURN,)*len(sources),tuple(s.meta.perf.start_pc for s in sources),'fresh consumers are the actual new return instruction')
        for s in sources:
            program=self.owned_program(s)
            self.check(call_address(NEW_CALL),program.head.address,'fresh return owns new live frame, never cancelled old version')
        self.check(call_address(NEW_CALL),self.model.program.head.address,'new frame survives the checked final returns')
        self.check(call_address(NEW_CALL),self.model.committed[self.model.committed_head].address,'retained new frame agrees with speculative program')
        self.check(self.frozen,tuple(s.meta.redirect['ras'] for s in self.originals),'all full/guard original metadata remains immutable')
        self.mark(7,sources[-1].meta_tick)

    def finish(self):
        self.raise_failure()
        if self.closed:return
        super().finish()
        self.check(set(range(len(RULES))),self.reached,'all actual lifetime and consumer obligations must close')
        self.check(None,self.model.pending_retirement,'no unobserved retirement effect')
        for rule in RULES:self.lifecycle.record('checked',rule,self.last_actual[2])
        self.lifecycle.finish();self.closed=True
