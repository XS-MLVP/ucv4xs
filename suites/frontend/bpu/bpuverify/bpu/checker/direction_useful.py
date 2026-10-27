"""Independently expected useful effects need actual service and new consumers."""
from copy import deepcopy

from bpuverify.bpu.checker.direction_forwarding import DirectionForwardingChecks
from bpuverify.bpu.coverage.direction_useful import RULES
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS
from bpuverify.bpu.model.tage.service import learning_inflight
from bpuverify.bpu.model.tage.useful_service import PROGRAM,pending_useful,occupancy


class DirectionUsefulChecks(DirectionForwardingChecks):
    def __init__(self,pipeline,coverage):
        super().__init__(pipeline,coverage)
        self.program=PROGRAM;self.table,self.bank=7,PC%4
        self.plan=();self.contexts=();self.original_metadata=()
        self.input_ticks=[];self.proposals=[];self.written=[]
        self.holding=False;self.last=None;self.pending_checked=False;self.release_tick=None
        self.old_sources={};self.new_sources={}

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def read(self,source):return self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read

    def useful(self,source):
        read=self.read(source)
        values=[]
        for position in POSITIONS:
            matches=read.matches(position)
            self.check(((7,len(values)),),tuple(match[:2] for match in matches),'exact original longest-history owners')
            values.append(matches[-1][3])
        return tuple(values)

    def arm(self,sources):
        self.check((),self.sources,'useful service arms once')
        self.check(len(PROGRAM.feedback_order),len(sources),'four distinct original A/B/A/B sources before feedback')
        tokens=tuple(self.values(source)[0] for source in sources)
        self.check(len(tokens),len({id(token.history) for token in tokens}),'distinct immutable checkpoint owners')
        reads=tuple(self.read(source) for source in sources)
        self.check(True,reads[0].context!=reads[1].context and reads[0].rows[7]!=reads[1].rows[7],
            'two genuine histories and distinct useful rows, not duplicate labels')
        self.check((reads[0],reads[1]),(reads[2],reads[3]),'revisited histories retain identical original reads')
        for index,(source,token) in enumerate(zip(sources,tokens,strict=True)):
            if index:self.check(True,sources[index-1].meta_tick<source.prediction_tick,'each old source is independently accepted')
            self.prepared(source,(PROGRAM.initial_base,PROGRAM.initial_counters))
            self.check(PROGRAM.initial_useful,self.useful(source),'target useful zero and learned neighbour useful one')
            metadata=self.pipeline.model.sources.defined_metadata(token)
            entries=tuple(entry for row in source_entries(token.lookup) for entry in row)
            for slot,entry in enumerate(entries):
                if entry.hit and entry.position==POSITIONS[0]:
                    self.check((1,0,1,0),(metadata[f'{slot}.useProvider'],metadata[f'{slot}.hasAlt'],
                        metadata[f'{slot}.altOrBasePred'],int(metadata[f'{slot}.providerTakenCtr_value']>=4)),
                        'negative provider is correct against a positive original base, without a reread')
        self.sources=tuple(sources);self.contexts=tuple(read.context for read in reads[:2])
        self.original_metadata=tuple(deepcopy(self.pipeline.model.sources.defined_metadata(token)) for token in tokens)
        self.plan=tuple(dict(row=read.rows[7],value=1) for read in reads)

    def begin_read_window(self):
        self.check(4,len(self.sources),'source qualification precedes continuous read service')
        self.check(False,self.holding,'one read window')
        self.holding=True

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last=event.tick,row
            self.check(False,bool(row['reset']),'reset cannot erase an experiment')
            self.check((0,0),row['flushes'],'maintenance cannot silently erase useful obligations')
            if self.holding:
                self.check(True,any(port['valid'] and port['mask']&(1<<self.bank) for port in row['reads']),
                    'every cycle retains same-bank read pressure')
                self.check((0,0),tuple(port['ready'] for port in row['writes']),'reads deny both useful service ports')
                self.check(0,row['reads'][1]['valid'],'the original strong feedback does not reread SRAM')
                if row['training']['valid'] and row['training']['ready']:
                    pred=row['prediction']
                    self.check(True,bool(pred['valid'] and pred['ready'] and pred['pc']%4==self.bank),
                        'public prediction and feedback accept together')
                    self.input_ticks.append(event.tick)
            flags=tuple(port['valid'] for port in row['incoming'])
            if any(flags):
                self.check(True,self.holding and not self.pending_checked,'all proposals belong to the declared blocked learning phase')
                self.check((1,0),flags,'only the disagreed correct provider learns usefulness')
                ordinal=len(self.proposals)
                self.check(True,ordinal<len(self.plan),'no extra useful effect')
                port=row['incoming'][0]
                self.check(1,port['ready'],'bounded source set is accepted without useful overflow')
                self.check(self.plan[ordinal],port['bits'],'complete original-history useful proposal')
                if ordinal:self.check(self.proposals[-1][0]+2,event.tick,'all original learning effects remain adjacent')
                self.proposals.append((event.tick,deepcopy(port['bits'])))
            if self.pending_checked and self.holding:self.check_blocked(row)
        except Exception as error:self.failure=error

    def check_blocked(self,row):
        self.check((dict(valid=1,ready=0,bits=self.plan[0]),dict(valid=0,ready=0)),
            (row['writes'][0],{key:row['writes'][1][key] for key in ('valid','ready')}),
            'full useful sequence remains blocked behind its original first effect')
        self.check((len(self.plan),0),tuple(occupancy(q) for q in row['queues']),
            'all four pending useful effects retained, unrelated owner remains empty')

    def accepted_burst(self,events):
        self.check((),self.accepted,'one input burst')
        self.check(4,len(events),'every original source has an actual acceptance')
        for index,(source,(tick,resolution)) in enumerate(zip(self.sources,events,strict=True)):
            self.check(True,tick>source.meta_tick and resolution.origin is self.pipeline.source_token(source),
                'exact source owns its accepted feedback')
            if index:self.check(events[index-1][0]+2,tick,'adjacent actual driver accepts')
            self.check((PC,((POSITIONS[0],TARGETS[0],1,False,False,0),(POSITIONS[1],TARGETS[1],1,True,False,0))),
                (resolution.pc,tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict,int(b.action))
                    for b in resolution.branches if b is not None)),'complete executed prefix and taken tail')
            self.check(False,self.pipeline.model.sources.feedback_for(resolution).reread,'owned source independently qualifies non-reread')
        self.check(tuple(tick for tick,_ in events),tuple(self.input_ticks),'driver receipts equal monitored public accepts')
        controls=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(controls[0],bool(controls[1][2] and controls[1][3])),
            'both predictors enabled at real acceptance')
        self.accepted=tuple(events)
        # A prepared disagreement is not yet a correct resolved outcome.
        # Reach both events only at the actual associated input acceptance.
        for rule in RULES[:2]:self.coverage.record('reached',rule,events[-1][0])

    def pending(self):
        self.check(False,self.pending_checked,'one mature pending checkpoint')
        self.check(4,len(self.accepted),'accepted sources precede pending effects')
        tage=self.pipeline.model.sources.tage
        self.check(False,learning_inflight(tage),'all offered learning has matured, not merely been accepted')
        self.check((self.plan,()),pending_useful(tage,self.table,self.bank),'independent useful sequence equals hand-derived original outcomes')
        self.check(0,tage.useful_queue[self.table,self.bank,0].drops,'this bounded program has no overflow waiver')
        self.check(self.plan,tuple(payload for _,payload in self.proposals),'every complete actual enqueue compared in order')
        self.check(True,all(proposal[0]>accepted[0] for proposal,accepted in zip(self.proposals,self.accepted,strict=True)),
            'each actual effect follows its own accepted input')
        self.check([],self.written,'no useful SRAM commit before read release')
        self.check(self.pipeline.last_tick,self.last[0],'pending reference and actual row share one exact boundary')
        self.check_blocked(self.last[1]);self.pending_checked=True
        self.coverage.record('reached',RULES[2],self.last[0])

    def old_consumed(self,source):
        self.check(True,self.pending_checked and self.holding,'old visibility follows complete blocked learning')
        self.check(True,source.prediction_tick>self.accepted[-1][0],'old read is a fresh accepted query')
        context=self.read(source).context
        self.check(True,context in self.contexts and context not in self.old_sources,'one old read for each original history')
        self.prepared(source,(PROGRAM.final_base,PROGRAM.initial_counters))
        self.check(PROGRAM.initial_useful,self.useful(source),'new requests still consume old useful under read pressure')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete old consumer repair window')
        self.check([],self.written,'no hidden useful write opportunity')
        self.check_blocked(self.last[1]);self.old_sources[context]=source
        if len(self.old_sources)==2:self.coverage.record('reached',RULES[3],source.meta_tick)

    def release(self):
        self.check(2,len(self.old_sources),'both histories consumed old state before releasing reads')
        self.check(None,self.release_tick,'one read release')
        self.release_tick=self.pipeline.last_tick;self.holding=False

    def write_accepted(self,way,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,
            'actual useful service follows declared read release')
        self.check(0,way,'only the qualified provider owner retires usefulness')
        ordinal=len(self.written);self.check(True,ordinal<len(self.plan),'every useful effect commits once')
        self.check(self.plan[ordinal],transfer.value,'SDK-confirmed complete useful write and FIFO order')
        self.written.append((transfer.accepted_tick,deepcopy(transfer.value)))
        if len(self.written)==len(self.plan):self.coverage.record('reached',RULES[4],transfer.accepted_tick)

    def new_consumed(self,source):
        self.check(4,len(self.written),'all actual useful commits precede final read')
        self.check(True,source.prediction_tick>self.written[-1][0],'fresh lookup after actual committed service')
        context=self.read(source).context
        self.check(True,context in self.contexts and context not in self.new_sources,'one new read per original history')
        self.prepared(source,(PROGRAM.final_base,PROGRAM.final_counters))
        self.check(PROGRAM.final_useful,self.useful(source),
            'both stale original effects store useful one, not lost zero or invented accumulated two')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete new consumer repair window')
        self.check(((),()),pending_useful(self.pipeline.model.sources.tage,self.table,self.bank),'all independent useful obligations drained')
        self.check((0,0),tuple(port['valid'] for port in self.last[1]['writes']),'no unconsumed actual useful write')
        self.check((0,0),tuple(occupancy(q) for q in self.last[1]['queues']),'both actual useful queues are empty after service')
        self.new_sources[context]=source
        if len(self.new_sources)==2:
            metadata=tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(old)) for old in self.sources)
            self.check(self.original_metadata,metadata,'old metadata remains immutable through delayed learning and new consumption')
            self.coverage.record('reached',RULES[5],source.meta_tick)
            for rule in RULES:self.coverage.record('checked',rule,source.meta_tick)
            for old in (*self.sources,*self.old_sources.values()):self.pipeline.retire_source(old.meta_tick)
            self.closed=True

    def finish(self):
        self.raise_failure();self.check(True,self.closed,'both fresh committed consumers and every actual service receipt are required')
        self.coverage.finish()
