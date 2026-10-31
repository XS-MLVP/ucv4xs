"""Check actual confidence at every update, including hold and reversal."""
from copy import deepcopy

from suites.frontend.bpu.bpu.checker.direction_turnaround import DirectionTurnaroundChecks
from suites.frontend.bpu.bpu.coverage.confidence_boundary import RULES
from suites.frontend.bpu.bpu.model.tage.confidence_boundary import PROGRAMS,CAPTURES,SOURCE_PROFILES,source_counts
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC
from suites.frontend.bpu.bpu.model.direction_sources import HISTORY_PORTS


class ConfidenceBoundaryChecks(DirectionTurnaroundChecks):
    programs=PROGRAMS
    rules=RULES
    capture_roles=CAPTURES
    source_profiles=SOURCE_PROFILES
    stream_pc=STREAM_PC^0x10

    def __init__(self,pipeline,coverage,program,*,traffic='returning'):
        if traffic not in ('returning','fallthrough'):raise ValueError('unknown read traffic semantics')
        super().__init__(pipeline,coverage,program)
        self.traffic=traffic
        self.prepare_read_stream=traffic=='returning'
        if traffic=='fallthrough':self.stream_pc=STREAM_PC+(1<<20)
        self.copies={role:[] for role in SOURCE_PROFILES}
        self.copy_counts=source_counts(program)
        self.confidence_steps=[]
        self.main_requests=[[],[]]
        self.training_histories=[]

    def prepared_source_count(self,role):return self.copy_counts[role]

    def retain_prepared(self,role,source):
        self.check(True,role in self.copies,'only declared original confidence epochs')
        copies=self.copies[role]
        self.check(True,len(copies)<self.copy_counts[role],'no undeclared extra prediction')
        if not copies:super().retain_prepared(role,source)
        else:
            self.check(self.profile(copies[0]),self.profile(source),'every additional source has the qualified original profile')
            self.check(self.read(copies[0]).context,self.read(source).context,
                       'each additional prediction owns the same original logical history')
            token=self.pipeline.source_token(source)
            self.check(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(copies[0])),
                       self.pipeline.model.sources.defined_metadata(token),'full original provider qualification preserved')
            self.check(True,copies[-1].meta_tick<source.prediction_tick,
                       'separate actual queries, not cloned public metadata')
            self.remember(source)
        owners=[self.pipeline.source_token(s).history for group in self.copies.values() for s in group]
        self.check(True,all(self.pipeline.source_token(source).history is not h for h in owners),
                   'each old result owns a different real prediction')
        copies.append(source)

    def arm_asymmetric(self,warm_source,warm_event,current):
        super().arm_asymmetric(warm_source,warm_event,current)
        self.check(self.copy_counts,{role:len(v) for role,v in self.copies.items()},'every declared source captured before migration')
        self.saved.update({f'{role}#{i}':s for role,group in self.copies.items() for i,s in enumerate(group)})
        self.reach(self.rules[15],actual_sources={name:dict(meta_tick=self.saved[name].meta_tick,
            prediction_tick=self.saved[name].prediction_tick,profile=self.profile(self.saved[name]))
            for name in self.program.late_sources})

    def fronts(self,row,plan,point):
        expected=tuple(dict(valid=int(bool(p)),ready=0,bits=p[0] if p else None) for p in self.concrete(plan))
        actual=tuple(dict(valid=p['valid'],ready=p['ready'],bits=p['bits'] if p['valid'] else None) for p in row['writes'])
        self.check(expected,actual,point)
        return deepcopy(actual)

    def late_input_cadence(self,previous,current):
        self.check(True,current>previous and (current-previous)%2==0,
                   'capacity-admitted asynchronous inputs retain actual rising order')

    def late_proposal_cadence(self,index,tick):
        self.check(self.offered[-1]['tick']+self.input_ticks[index]-self.input_ticks[index-1],tick,
                   'learning preserves the actual capacity-admitted input spacing')

    def capture_state(self,event,packet):
        phase=self.phase;index=len(self.offered)-3;input_index=len(self.input_ticks)
        super().capture_state(event,packet)
        if self.failure is not None or phase!='refill-holding':return
        try:
            row=packet['state']
            if row['training']['valid'] and row['training']['ready']:
                source=self.requests[input_index];token=self.pipeline.source_token(source)
                expected=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
                actual=tuple(packet['train_folds'])
                self.check(expected,actual,'original training history must remain reconstructible; stale PHR is not a TAGE arithmetic defect')
                self.training_histories.append(dict(tick=event.tick,meta_tick=source.meta_tick,
                                                    original=expected,actual=actual))
            for align,row in enumerate(packet['main']):
                if row['direction']['valid']:
                    self.check(1,row['direction']['ready'],
                               'long TAGE backlog must not silently discard auxiliary Main direction learning')
                    self.main_requests[align].append(dict(tick=event.tick,competing_read=row['read']['valid'],
                                                         bits=deepcopy(row['direction']['bits'])))
            if len(self.offered)==index+4:
                actual=self.fronts(packet['state'],self.program.pending_before(index),
                                   'each current confidence BEFORE the next old proposal; no wrap or old-value reset')
                self.confidence_steps.append(dict(index=index,tick=event.tick,compared=actual))
        except Exception as error:self.failure=error

    def pending(self):
        late=self.phase=='refill-holding'
        super().pending()
        if not late:return
        self.check(len(self.program.late_sources),len(self.confidence_steps),'every intermediate confidence mandatory')
        self.check(True,self.last[0]>self.offered[-1]['tick'],'final confidence is observed after the last proposal')
        actual=self.fronts(self.last[1],self.program.final_plan,'final saturated or reversed confidence is actually retained')
        self.reach(self.rules[16],steps=self.confidence_steps,final_tick=self.last[0],final_fronts=actual)
        counts=tuple(sum(any(index==align for index,_,_ in outcome) for outcome in self.program.late_outcomes)
                     for align in range(2))
        self.check(counts,tuple(map(len,self.main_requests)),'every auxiliary Main update has actual ready acceptance')
        self.check((0,0),tuple(self.pipeline.model.sources.main.directions[a,0].drops for a in range(2)),
                   'independent auxiliary Main queues also have zero drops')
        self.reach(self.rules[17],actual_main_acceptances=self.main_requests,counts=counts,independent_drops=(0,0))
        self.check(len(self.program.late_sources),len(self.training_histories),'every original training history compared')
        self.reach(self.rules[18],actual_histories=self.training_histories,traffic=self.traffic)
