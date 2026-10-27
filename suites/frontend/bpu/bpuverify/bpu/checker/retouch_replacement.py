"""Logical access policy, complete actual versions, real services and consumers."""
from copy import deepcopy

from toffee import CheckContext,ScoreboardMode,XEvent,XPhase
from bpuverify.bpu.checker.direction_service import DirectionServiceChecks
from bpuverify.bpu.coverage.retouch_replacement import RULES
from bpuverify.bpu.model.direction_sources import HISTORY_PORTS
from bpuverify.bpu.model.tage.retouch_replacement import READ_STREAM
from bpuverify.bpu.model.tage.service import learning_inflight,pending_plan
from bpuverify.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS


class RetouchReplacementChecks(DirectionServiceChecks):
    observe_retention=True
    stream_pc=READ_STREAM

    def __init__(self,pipeline,coverage,program):
        if program not in coverage.programs:raise ValueError('unknown retouch replacement program')
        super().__init__(pipeline,coverage,program=program)
        self.phase='preparation'
        self.trace=program.trace()
        self.offered=[];self.effects=[];self.histories=[];self.main=[[],[]]
        self.awaiting=None;self.last_packet=None;self.last_launch=None
        self.completed=set();self.witnesses={}

    def check(self,expected,actual,point):
        self.raise_failure()
        try:
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
                self.pipeline.board.name,ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,
                request=dict(point=point,program=self.program.name,mode=self.program.mode,phase=self.phase,
                    desired_victim=self.program.victim,actual_inputs=self.actual_inputs,
                    actual_proposals=self.offered,actual_effects=self.effects,
                    latest_actual=self.last_packet,last_launch=self.last_launch,actual_services=self.written)))
        except Exception as error:self.failure=error;raise

    def reach(self,index,**witness):
        rule=RULES[index];self.completed.add(rule);self.witnesses[rule]=deepcopy(witness)
        self.coverage.record('reached',rule,**witness)

    def arm(self,sources):
        super().arm(sources)
        self.keys={}
        for history in range(5):
            source=self.sources[self.program.feedback_order.index(history)]
            read=self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read
            self.keys[history]=tuple(dict(row=read.rows[self.table],valid=1,tag=read.entries[self.table][owner].tag)
                                     for owner in range(2))
        self.expected_offers=tuple(tuple(None if owner not in self.program.input_owners(i) else
            dict(self.keys[h][owner],counter=(max(0,self.program.initial_counters(h)[0]-1)
            if owner==0 else min(7,self.program.initial_counters(h)[1]+1))) for owner in range(2))
            for i,h in enumerate(self.program.feedback_order))
        self.expected_plan=self.plan(self.trace[-1])
        self.frozen=tuple(deepcopy(s.meta) for s in self.sources)
        self.defined=tuple(deepcopy(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))) for s in self.sources)
        self.initial_overflows=self.pipeline.model.sources.tage.cache[self.table,self.bank].overflows
        self.reach(0,sources=[dict(history=h,meta_tick=s.meta_tick,profile=self.values(s)[1])
            for h,s in zip(self.program.feedback_order,self.sources,strict=True)],contract='learning',
            expected_victim=self.program.victim,independent_final=self.expected_plan)

    def plan(self,snapshot):
        return tuple(tuple(dict(self.keys[r.history][owner],counter=r.counter)
            for r in self.program.owner_records(snapshot,owner) if r is not None) for owner in range(2))

    def before(self,index):return self.program.empty_state if index==0 else self.trace[index-1]

    def compare_retained(self,packet,snapshot,point):
        expected_dirty=tuple(tuple(int(r is not None) for r in self.program.owner_records(snapshot,o)) for o in range(2))
        self.check(expected_dirty,tuple(tuple(r) for r in packet['state']['dirty']),point+' dirty lifetimes')
        for owner in range(2):
            for rank,record in enumerate(self.program.owner_records(snapshot,owner)):
                if record is not None:
                    expected=dict(shadow=1,**self.keys[record.history][owner],counter=record.counter)
                    self.check(expected,packet['retained'][owner][rank],point+' complete owned version')
        fronts=tuple(dict(valid=int(bool(p)),ready=0,bits=p[0] if p else None) for p in self.plan(snapshot))
        observed=tuple(dict(valid=p['valid'],ready=p['ready'],bits=p['bits'] if p['valid'] else None)
                       for p in packet['state']['writes'])
        self.check(fronts,observed,point+' complete blocked service fronts')

    def begin_read_window(self):
        super().begin_read_window();self.phase='holding'

    def capture_state(self,event,packet):
        if self.failure is not None:return
        try:
            row=packet['state'];self.last=(event.tick,row);self.last_packet=deepcopy(packet)
            self.check(0,row['reset'],'no reset substitutes for retained learning')
            if not self.holding:return
            busy=any(p['valid'] and p['mask']&(1<<self.bank) for p in row['reads'])
            self.check((True,0,(0,0)),(bool(busy),row['reads'][1]['valid'],tuple(p['ready'] for p in row['writes'])),
                       'normal prediction reads block both TAGE services without reread')
            self.busy_samples+=1
            if self.awaiting is not None and event.tick>self.awaiting[0]:
                _,index=self.awaiting
                self.compare_retained(packet,self.trace[index],'post-learning')
                self.effects.append(dict(index=index,tick=event.tick,retained=deepcopy(packet['retained'])))
                if index==3:self.reach(2,tick=event.tick,retained=packet['retained'])
                if index==len(self.trace)-2:self.reach(3,effects=self.effects[4:],retained=packet['retained'])
                if index==len(self.trace)-1:self.reach(4,tick=event.tick,retained=packet['retained'],
                    victim=self.program.victim,expected_plan=self.expected_plan)
                self.awaiting=None
            if row['training']['valid'] and row['training']['ready']:
                index=len(self.actual_inputs);self.check(True,index<len(self.sources),'only declared original input')
                pred=row['prediction'];self.check((1,1,self.bank),(pred['valid'],pred['ready'],pred['pc']%4),
                    'real prediction accepts alongside every input')
                token=self.pipeline.source_token(self.sources[index])
                expected=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
                self.check(expected,tuple(packet['train_folds']),'every original training history still reconstructs')
                self.actual_inputs.append(event.tick);self.histories.append(dict(tick=event.tick,folds=expected))
            for align,main in enumerate(packet['main']):
                if main['direction']['valid']:
                    self.check(1,main['direction']['ready'],'auxiliary Main update cannot be dropped')
                    self.main[align].append(dict(tick=event.tick,bits=deepcopy(main['direction']['bits'])))
            if any(p['valid'] for p in row['incoming']):
                index=len(self.offered)
                self.check(True,index<len(self.trace) and index<len(self.actual_inputs),'one proposal per accepted source')
                self.check(tuple(int(p is not None) for p in self.expected_offers[index]),
                    tuple(p['valid'] for p in row['incoming']),'exact declared branch subset, no invented neighbor feedback')
                self.check(self.expected_offers[index],tuple(p['bits'] if p['valid'] else None for p in row['incoming']),
                           'old source supplies its own initial proposal, not retained counter seed')
                self.check(True,event.tick>self.actual_inputs[index],'proposal follows its own actual input')
                self.compare_retained(packet,self.before(index),'pre-learning')
                self.check(None,self.awaiting,'previous update has actual post-state before next proposal')
                self.awaiting=(event.tick,index)
                self.offered.append(dict(tick=event.tick,bits=deepcopy(tuple(p['bits'] for p in row['incoming']))))
        except Exception as error:self.failure=error

    def accepted_burst(self,events):
        self.check((),self.accepted,'one complete asynchronous send group')
        self.check(len(self.sources),len(events),'every source has an actual receipt')
        for index,(source,(tick,resolution)) in enumerate(zip(self.sources,events,strict=True)):
            self.check(True,tick>source.meta_tick and resolution.origin is self.pipeline.source_token(source),
                       'accepted feedback retains its original owner')
            if index:self.check(True,tick>events[index-1][0] and (tick-events[index-1][0])%2==0,
                                'capacity-admitted inputs retain rising order')
            self.check(False,self.pipeline.model.sources.feedback_for(resolution).reread,'each old source qualifies without reread')
            expected=PC,tuple((POSITIONS[b],TARGETS[b],1,taken,wrong,0)
                for b,taken,wrong in self.program.branch_outcomes(index))
            actual=resolution.pc,tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict,int(b.action))
                                       for b in resolution.branches if b is not None)
            self.check(expected,actual,'complete actual NT prefix and taken tail')
        self.check(tuple(t for t,_ in events),tuple(self.actual_inputs),'driver receipts equal actual input monitor')
        self.check(True,self.last_launch is not None,'final new source has an actual launch opportunity')
        self.check(self.last_launch['tick']+2,events[-1][0],'final receipt follows its compared launch')
        self.check(self.program.mode=='overlapped',self.last_launch['learning_inflight'],
                   'overlap versus settled learning is an actual boundary, not a label')
        self.accepted=tuple(events)
        self.reach(1,accepted_ticks=self.actual_inputs,histories=self.histories,last_launch=self.last_launch)

    def pending(self):
        self.raise_failure()
        self.check(len(self.trace),len(self.effects),'every complete actual retained transition mandatory')
        self.check(None,self.awaiting,'last update has a fresh post-state')
        self.check(False,learning_inflight(self.pipeline.model.sources.tage),'learning matured separately from admission')
        self.check(self.expected_plan,pending_plan(self.pipeline.model.sources.tage,self.table,self.bank),
                   'explicit learning-policy reference agrees with independent logical-group model')
        self.check(self.initial_overflows+2,self.pipeline.model.sources.tage.cache[self.table,self.bank].overflows,
                   'only one old obligation per original owner is superseded')
        self.check(self.program.main_update_counts,tuple(map(len,self.main)),'all and only declared auxiliary Main requests actually accepted')
        self.check((0,0),tuple(self.pipeline.model.sources.main.directions[a,0].drops for a in range(2)),
                   'independent Main queues have no drop')
        self.expected_pending=tuple(p[0] for p in self.expected_plan)
        self.reach(5,actual_main=self.main,independent_drops=(0,0))

    def old_consumed(self,source):
        token,values=self.values(source);context=self.pipeline.model.sources.snapshot(token).read.context
        self.check(True,context in self.contexts and context not in self.old_sources,'one fresh old-value consumer per history')
        history=self.contexts.index(context)
        self.check((self.program.initial_base,self.program.initial_counters(history)),values,'old Main/TAGE storage preserved under read competition')
        self.check(True,source.prediction_tick>self.accepted[-1][0] and self.holding,'old consumer precedes service and follows all inputs')
        self.check(((7,0),(7,1)),self.owners(token),'old complete provider identities')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'old complete correction window')
        self.compare_retained(self.last_packet,self.trace[-1],'old-consumer preservation')
        self.old_sources[context]=source
        if len(self.old_sources)==5:self.reach(6,consumers={str(self.contexts.index(c)):dict(meta_tick=s.meta_tick,
            prediction_tick=s.prediction_tick,profile=self.values(s)[1]) for c,s in self.old_sources.items()})

    def release(self):
        self.check(5,len(self.old_sources),'all blocked consumers precede release')
        self.check(None,self.release_tick,'one declared service release')
        self.release_tick=self.pipeline.last_tick;self.holding=False;self.phase='service'

    def write_accepted(self,owner,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,'real write follows release')
        self.check(True,owner in (0,1),'one original provider owner')
        index=len(self.written[owner]);self.check(True,index<4,'no victim or extra service')
        self.check(self.expected_plan[owner][index],transfer.value,'complete actual survivor identity and current counter')
        self.check(True,isinstance(transfer.event,XEvent) and transfer.event.phase is XPhase.RISING_STABLE,
                   'SDK confirms actual rising acceptance')
        self.written[owner].append((transfer.accepted_tick,deepcopy(transfer.value)))
        if tuple(map(len,self.written.values()))==(4,4):self.reach(7,actual_services=self.written)

    def new_consumed(self,source):
        token,values=self.values(source);context=self.pipeline.model.sources.snapshot(token).read.context
        self.check((4,4),tuple(map(len,self.written.values())),'all eight real services precede new consumers')
        self.check(True,context in self.contexts and context not in self.new_sources,'one final consumer per logical history')
        history=self.contexts.index(context)
        self.check((self.program.initial_base,self.program.expected_counters(history)),values,
                   'victim retains old SRAM; every survivor and new history consume their own result')
        self.check(((7,0),(7,1)),self.owners(token),'complete final provider identities')
        self.check(True,source.prediction_tick>max(t for events in self.written.values() for t,_ in events),'fresh consumer after all SDK acceptances')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete final correction window')
        self.new_sources[context]=source
        if len(self.new_sources)==5:self.reach(8,consumers={str(self.contexts.index(c)):dict(meta_tick=s.meta_tick,
            prediction_tick=s.prediction_tick,profile=self.values(s)[1]) for c,s in self.new_sources.items()})

    def finish(self):
        self.check(False,self.closed,'single-use closure')
        self.check((5,5),(len(self.old_sources),len(self.new_sources)),'all ten real history consumers')
        self.check((4,4),tuple(map(len,self.written.values())),'all complete service receipts retained at closure')
        self.check(((),()),pending_plan(self.pipeline.model.sources.tage,self.table,self.bank),'all surviving effects drained')
        self.check((0,0),tuple(p['valid'] for p in self.last[1]['writes']),'no extra actual service remains')
        self.check(self.frozen,tuple(s.meta for s in self.sources),'complete original snapshots immutable')
        self.check(self.defined,tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s)) for s in self.sources),
                   'independent original definitions immutable')
        self.reach(9,original_meta_ticks=[s.meta_tick for s in self.sources],compared_consumers=10)
        self.check(set(RULES),self.completed,'every semantic obligation precedes checked credit')
        for rule in RULES:self.coverage.record('checked',rule,**self.witnesses[rule])
        self.closed=True
        retired=set()
        for s in (*self.sources,*self.old_sources.values(),*self.new_sources.values()):
            if s.meta_tick not in retired:self.pipeline.retire_source(s.meta_tick);retired.add(s.meta_tick)
