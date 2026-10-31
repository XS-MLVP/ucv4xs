"""Read priority preserves owned learning obligations without early visibility."""
from suites.frontend.bpu.bpu.checker.direction_forwarding import DirectionForwardingChecks
from suites.frontend.bpu.bpu.coverage.direction_service import RULES
from suites.frontend.bpu.bpu.model.tage.forwarding import PC,POSITIONS,TARGETS
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight,pending_plan,READ_PRIORITY_PAIR


class DirectionServiceChecks(DirectionForwardingChecks):
    def __init__(self,pipeline,coverage,*,program=READ_PRIORITY_PAIR):
        super().__init__(pipeline,coverage)
        self.program=program
        self.rules=getattr(coverage,'rules',RULES)
        self.table,self.bank=7,PC%4
        self.holding=False
        self.last=None
        self.actual_inputs=[]
        self.busy_samples=0
        self.expected_pending=None
        self.expected_plan=None
        self.contexts=()
        self.old_sources={}
        self.new_sources={}
        self.release_tick=None
        self.written={0:[],1:[]}

    def arm(self,sources):
        self.check((),self.sources,'read-priority experiment arms once')
        self.check(len(self.program.feedback_order),len(sources),'one genuine old source per planned semantic input')
        tokens=tuple(self.values(source)[0] for source in sources)
        self.check(len(sources),len({id(token.history) for token in tokens}),'distinct checkpoint owners, not duplicated receipts')
        for earlier,later in zip(sources,sources[1:]):
            self.check(True,earlier.meta_tick<later.prediction_tick,'query order matches subsequent feedback order')
        reads=tuple(self.pipeline.model.sources.snapshot(token).read for token in tokens)
        by_history={}
        for index,read in zip(self.program.feedback_order,reads,strict=True):
            if index in by_history:self.check(by_history[index],read,'a revisited history owns identical old content')
            else:by_history[index]=read
        ordered=tuple(by_history[index] for index in range(self.program.history_count))
        self.check(self.program.history_count,len({read.context for read in ordered}),'genuine paths have distinct history contexts')
        self.check(self.program.history_count,len({read.rows[self.table] for read in ordered}),
            'all histories identify distinct SRAM rows in the same bank')
        for history,source,token in zip(self.program.feedback_order,sources,tokens,strict=True):
            self.prepared(source,(self.program.initial_base,self.program.initial_counters(history)))
            self.check(((7,0),(7,1)),self.owners(token),'both longest-history owners retained in both contexts')
            metadata=self.pipeline.model.sources.defined_metadata(token)
            entries=tuple(entry for row in source_entries(token.lookup) for entry in row)
            for slot,entry in enumerate(entries):
                if entry.hit and entry.position in POSITIONS:
                    self.check((1,0),(metadata[f'{slot}.useProvider'],metadata[f'{slot}.hasAlt']),
                        'every old strong provider avoids a training SRAM reread')
        self.contexts=tuple(read.context for read in ordered)
        self.sources=tuple(sources)

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def begin_read_window(self):
        self.check(len(self.program.feedback_order),len(self.sources),'all old sources prepared before read-priority experiment')
        self.check(False,self.holding,'one continuous read window')
        self.holding=True

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last=event.tick,row
            busy=any(port['valid'] and port['mask']&(1<<self.bank) for port in row['reads'])
            if busy:
                self.check((0,0),tuple(port['ready'] for port in row['writes']),'SRAM read priority denies both write ports')
            if not self.holding:return
            self.check(False,bool(row['reset']),'reset cannot silently replace an in-flight service experiment')
            self.check(True,bool(busy),'continuous same-bank read service, not a hidden write opportunity')
            self.check(0,row['reads'][1]['valid'],'the concurrent feedback never requests a tagged SRAM reread')
            self.busy_samples+=1
            if row['training']['valid'] and row['training']['ready']:
                prediction=row['prediction']
                self.check(True,bool(prediction['valid'] and prediction['ready'] and prediction['pc']%4==self.bank),
                    'a real same-bank prediction is accepted with each feedback beat')
                self.actual_inputs.append(event.tick)
            if self.expected_pending is not None:self.check_pending_row(row)
        except Exception as error:self.failure=error

    def check_pending_row(self,row):
        self.check(tuple(dict(valid=1,ready=0,bits=payload) for payload in self.expected_pending),
            tuple(row['writes']),'both complete pending versions remain blocked and stable')

    def accepted_burst(self,events):
        self.check(len(self.program.feedback_order),len(self.sources),'all old sources must be armed first')
        self.check((),self.accepted,'one interleaved input burst')
        self.check(len(self.sources),len(events),'all complete input acceptances')
        for index,(source,(tick,resolution)) in enumerate(zip(self.sources,events,strict=True)):
            self.check(True,tick>source.meta_tick,'actual input follows its exact source')
            if index:self.check(events[index-1][0]+2,tick,'all planned inputs accepted on adjacent cycles')
            token=self.pipeline.source_token(source)
            self.check(True,resolution.origin is token,'acceptance keeps original checkpoint ownership')
            self.check((PC,((POSITIONS[0],TARGETS[0],1,False,False,0),(POSITIONS[1],TARGETS[1],1,True,False,0))),
                (resolution.pc,tuple((branch.position,branch.target,int(branch.kind),branch.taken,branch.mispredict,
                    int(branch.action)) for branch in resolution.branches if branch is not None)),
                'each accepted input resolves the complete NT prefix and T tail')
        controls=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(controls[0],bool(controls[1][2] and controls[1][3])),
            'both predictors genuinely enabled during concurrent input')
        self.check(tuple(tick for tick,_ in events),tuple(self.actual_inputs),'monitored concurrent input identities')
        self.check(True,self.busy_samples>0,'read service has actual samples')
        self.accepted=tuple(events)
        self.credit_inputs(events[-1][0])

    def credit_inputs(self,tick):
        for rule in self.rules[:2]:self.coverage.record('reached',rule,tick)

    def pending(self):
        self.raise_failure()
        self.check(None,self.expected_plan,'pending obligations frozen once, not rebased to actual writes')
        tage=self.pipeline.model.sources.tage
        self.check(False,learning_inflight(tage),'learning matured; acceptance is not commit')
        plan=pending_plan(tage,self.table,self.bank)
        expected={}
        for history in self.program.retained_histories:
            source=self.sources[self.program.feedback_order.index(history)]
            read=self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read
            for owner in range(2):
                payload=dict(row=read.rows[self.table],valid=1,tag=read.entries[self.table][owner].tag,
                    counter=self.program.expected_counters(history)[owner])
                expected[owner,payload['row'],payload['tag']]=payload
        actual={(owner,payload['row'],payload['tag']):payload for owner,way in enumerate(plan) for payload in way}
        self.check(expected,actual,'every independent history/owner obligation has the closed-form final counter')
        self.check((self.program.retained_count,)*2,tuple(map(len,plan)),'one pending version per retained history per owner')
        self.expected_plan=plan
        self.expected_pending=tuple(way[0] for way in plan)
        self.check(self.pipeline.last_tick,self.last[0],'service and pipeline snapshots share one exact boundary')
        self.check_pending_row(self.last[1])
        self.coverage.record('reached',self.rules[2],self.last[0])

    def old_consumed(self,source):
        self.check(True,self.expected_pending is not None,'pending writes precede the old-value consumer')
        self.check(True,source.prediction_tick>self.accepted[-1][0],'old-value observation is a new query, not an old receipt')
        token,values=self.values(source)
        context=self.pipeline.model.sources.snapshot(token).read.context
        self.check(True,context in self.contexts and context not in self.old_sources,'one new old-value consumer per original history')
        self.check(self.program.initial_counters(self.contexts.index(context)),values[1],
            'new read retains its original SRAM entries while both writes are blocked')
        self.check(((7,0),(7,1)),self.owners(token),'old-value query retains both logical provider owners')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete old-value consumer repair window')
        self.check(True,self.holding,'old-value consumption must precede read release')
        self.check((0,0),tuple(len(self.written[way]) for way in range(2)),'no SRAM write accepted during uninterrupted reads')
        self.check_pending_row(self.last[1])
        self.old_sources[context]=source
        self.coverage.record('reached',self.rules[3],source.meta_tick)
        if len(self.old_sources)==self.program.history_count:
            # Blocked fronts and old readers do not prove the remaining
            # versions survived. That obligation closes only after ALL
            # actual service transfers and their new consumers compare.
            for rule in (*self.rules[:2],self.rules[3]):self.coverage.record('checked',rule,source.meta_tick)

    def release(self):
        self.check(self.program.history_count,len(self.old_sources),'every old-value history consumer must be checked before release')
        self.check(None,self.release_tick,'read release is declared once')
        self.release_tick=self.pipeline.last_tick
        self.holding=False
        for rule in self.rules[4:]:self.coverage.record('reached',rule,self.release_tick)

    def write_accepted(self,way,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,'write may retire only after read release')
        self.check(True,way in (0,1),'committed port belongs to one original owner')
        ordinal=len(self.written[way])
        self.check(True,ordinal<len(self.expected_plan[way]),'each history/owner retires once, no extra write')
        self.check(self.expected_plan[way][ordinal],transfer.value,'SDK-confirmed full committed payload and service order')
        self.written[way].append((transfer.accepted_tick,transfer.value))

    def new_consumed(self,source):
        self.check(True,self.release_tick is not None and len(self.old_sources)==self.program.history_count,
            'every old history checked before release and new visibility')
        self.check((self.program.retained_count,)*2,tuple(len(self.written[way]) for way in range(2)),
            'all actual commit handshakes precede final consumption')
        self.check(True,source.prediction_tick>max(event[0] for way in self.written.values() for event in way),
            'new query follows every accepted commit')
        token,values=self.values(source)
        context=self.pipeline.model.sources.snapshot(token).read.context
        self.check(True,context in self.contexts and context not in self.new_sources,'one committed consumer per original owned history')
        self.check(self.program.expected_counters(self.contexts.index(context)),values[1],
            'new SRAM visibility contains the independently counted history-specific learning results')
        self.check(((7,0),(7,1)),self.owners(token),'commit preserves both original provider identities')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete committed consumer repair window')
        self.check((0,0),tuple(port['valid'] for port in self.last[1]['writes']),'no unconsumed extra pending update')
        self.check(((),()),pending_plan(self.pipeline.model.sources.tage,self.table,self.bank),'all owned writes actually drained')
        self.new_sources[context]=source
        if len(self.new_sources)==self.program.history_count:
            for rule in (self.rules[2],*self.rules[4:]):self.coverage.record('checked',rule,source.meta_tick)
            for old in (*self.sources,*self.old_sources.values()):self.pipeline.retire_source(old.meta_tick)
            self.closed=True

    def finish(self):
        self.check(True,self.closed,'old visibility, actual retirement and new visibility are all required')
        self.coverage.finish()
