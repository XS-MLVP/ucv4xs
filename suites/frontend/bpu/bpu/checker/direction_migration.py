"""A delayed strong source cannot overwrite today's neighbour in its old way."""
from toffee import CheckContext,ScoreboardMode
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.tage.migration import PC,POSITION,TARGET,PATHS,preparation
from suites.frontend.bpu.bpu.coverage.direction_migration import RULES


class DirectionMigrationChecks:
    observe_retention=True

    def __init__(self,pipeline,coverage,original_way):
        self.intents=tuple(preparation(original_way))
        self.pipeline,self.coverage,self.original_way=pipeline,coverage,original_way
        self.rules=getattr(coverage,'rules',RULES)
        self.commit_counters=(5,)
        self.table,self.bank=7,PC%4
        self.prepared_labels=[]
        self.preparing=None
        self.original=None
        self.original_metadata=None
        self.before=None
        self.proposal=None
        self.commit=None
        self.proposal_tick=None
        self.input_ticks=[]
        self.written=[]
        self.replay_event=None
        self.consumers={}
        self.failure=None
        self.closed=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
            self.pipeline.board.name,ScoreboardMode.DIRECT,request=dict(point=point,original_way=self.original_way,
                preparation=self.prepared_labels,replay=self.replay_event,proposal_tick=self.proposal_tick,written=self.written)))
        except Exception as error:self.failure=error;raise

    def read(self,source):return self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read

    def value(self,source):
        token=self.pipeline.source_token(source)
        entries=tuple(entry for row in source_entries(token.lookup) for entry in row)
        matches=tuple((slot,entry) for slot,entry in enumerate(entries) if entry.hit and entry.position==POSITION)
        self.check(1,len(matches),'one independently owned conditional MainBTB record')
        slot,entry=matches[0]
        self.check((PC,POSITION,TARGET,1),(token.pc,entry.position,token.lookup.values()[f'{slot}.target'],entry.kind),
            'exact semantic branch PC/position/target/type')
        read=self.read(source)
        providers=() if read is None else read.matches(POSITION)
        self.check(True,len(providers)<=1,'only the deliberately allocated longest-history provider')
        return entry.counter,None if not providers else providers[0]

    def preparing_input(self,source,intent):
        self.check(None,self.preparing,'each preparation effect must be consumed before the next')
        self.check(True,len(self.prepared_labels)<len(self.intents),'preparation is a bounded program, not an unqualified replay loop')
        self.check(self.intents[len(self.prepared_labels)],intent,'all semantic preparation steps in declared order')
        token=self.pipeline.source_token(source)
        predicted=self.pipeline.model.sources.snapshot(token,resolved=True).late.branch.taken
        self.check(intent.wrong,predicted!=intent.taken,'preparation misprediction agrees with the original semantic decision')
        self.preparing=source,intent

    def checked_outcome(self,event,source,taken,wrong):
        tick,resolution=event
        self.check(True,tick>source.meta_tick and resolution.origin is self.pipeline.source_token(source),
            'full accepted outcome belongs to the exact original public source')
        self.check((PC,((POSITION,TARGET,1,taken,wrong,0),)),(resolution.pc,tuple((b.position,b.target,
            int(b.kind),b.taken,b.mispredict,int(b.action)) for b in resolution.branches if b is not None)),
            'complete accepted semantic branch outcome')

    def prepared(self,source,intent,event):
        self.check(True,self.preparing is not None,'preparation input precedes its new consumer')
        before,planned=self.preparing
        self.check(planned,intent,'new consumer closes its own preparation input')
        self.checked_outcome(event,before,intent.taken,intent.wrong)
        self.check(True,source.prediction_tick>event[0],'preparation consumer follows accepted input')
        self.check(intent.expected,self.value(source),'hand-derived Main/TAGE preparation effects')
        if intent.label=='original':
            self.original=source
            self.original_metadata=tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(source)).items())
        self.prepared_labels.append(intent.label)
        self.preparing=None

    def arm(self,profile):
        self.check(tuple(s.label for s in self.intents),tuple(self.prepared_labels),'all real migrations prepared')
        self.check(None,self.before,'one delayed-source experiment')
        self.check(True,self.original is not None,'genuine original source retained before migration')
        self.check(set(PATHS),set(profile),'all three logical keys, not only the migrated one')
        self.check((3,(7,self.original_way,5,0)),self.value(self.original),'old provider owner/counter and agreeing taken base')
        expected=dict(original=(2,(7,1-self.original_way,4,0)),newcomer=(2,(7,self.original_way,5,1)),blocker=(2,None))
        for name,source in profile.items():self.check(expected[name],self.value(source),'current migrated/neighbor/displaced-key profile')
        reads={name:self.read(source) for name,source in profile.items()}
        self.check(3,len({r.context for r in reads.values()}),'three genuine history identities')
        self.check(1,len({r.rows[self.table] for r in reads.values()}),'intentional shared candidate row, not a bank/set sweep')
        old=self.read(self.original);current=reads['original']
        self.check(old.context,current.context,'migration preserves original logical history')
        tag=old.entries[self.table][self.original_way].tag
        self.check(tag,current.entries[self.table][1-self.original_way].tag,'migration preserves original logical tag')
        self.check(True,self.original.meta_tick<profile['original'].prediction_tick,'current owner is a genuinely later query')
        self.before=profile
        self.proposal=dict(row=old.rows[self.table],valid=1,tag=tag,counter=6)
        self.commit=dict(self.proposal,counter=5)
        self.coverage.record('reached',self.rules[0],max(s.meta_tick for s in profile.values()))

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.check(True,self.before is not None,'arm the logical owners before observing the replay')
            self.check(False,bool(row['reset']),'reset cannot replace a delayed-source experiment')
            self.check(0,row['reads'][1]['valid'],'original strong correct feedback must not reread SRAM')
            if row['training']['valid'] and row['training']['ready']:
                self.check([],self.input_ticks,'one actual replay input')
                self.input_ticks.append(event.tick)
            incoming=row['incoming'];flags=tuple(p['valid'] for p in incoming)
            if not any(flags):return
            self.check(tuple(int(way==self.original_way) for way in range(2)),flags,'proposal uses old requested way, not new owner')
            self.check(None,self.proposal_tick,'one complete delayed-source write proposal')
            self.check(self.proposal,incoming[self.original_way]['bits'],'proposal uses original snapshot counter 5 -> 6')
            self.proposal_tick=event.tick
            self.coverage.record('reached',self.rules[2],event.tick)
        except Exception as error:self.failure=error

    def write_accepted(self,way,transfer):
        self.check(True,self.proposal_tick is not None and transfer.accepted_tick>self.proposal_tick,
            'SDK write acceptance follows the original-source proposal')
        self.check([],self.written,'exactly one full committed effect')
        self.check(1-self.original_way,way,'retained logical owner wins over old requested port')
        self.check(self.commit,transfer.value,'current counter 4 -> 5, not old snapshot 5 -> 6')
        self.written.append((transfer.accepted_tick,way,transfer.value))
        self.coverage.record('reached',self.rules[3],transfer.accepted_tick)

    def accepted(self,event):
        self.raise_failure()
        self.check(True,self.before is not None,'original and current owners qualified before feedback acceptance')
        self.check(None,self.replay_event,'one associated original-source feedback')
        self.checked_outcome(event,self.original,True,False)
        self.check([event[0]],self.input_ticks,'actual public input acceptance matches its owned receipt')
        controls=self.pipeline.last_resolution_controls
        self.check((event[0],True),(controls[0],bool(controls[1][2] and controls[1][3])),'MainBTB/TAGE actually enabled for replay')
        self.check(False,self.pipeline.model.sources.feedback_for(event[1]).reread,'original metadata independently qualifies non-reread')
        self.replay_event=event
        self.coverage.record('reached',self.rules[1],event[0])

    def consumed(self,name,source):
        self.check(True,self.replay_event is not None and len(self.written)==len(self.commit_counters),
            'every actual input and actual commit precedes consumption')
        self.check(True,name in PATHS and name not in self.consumers,'one new consumer for each exact logical key')
        self.check(True,source.prediction_tick>self.written[-1][0],'consumer is a new post-commit lookup')
        self.check(self.read(self.before[name]).context,self.read(source).context,'consumer belongs to its original logical history')
        expected=dict(original=(3,(7,1-self.original_way,self.commit_counters[-1],0)),newcomer=(3,(7,self.original_way,5,1)),blocker=(3,None))
        self.check(expected[name],self.value(source),'migrated result, neighbour useful and displaced-key miss')
        self.check(((source.prediction_tick+2,2),),self.pipeline.corrections_for_source(source),'complete consumer repair sequence')
        self.consumers[name]=source
        if name=='original':self.coverage.record('reached',self.rules[4],source.meta_tick)
        if {'blocker','newcomer'}<=self.consumers.keys():self.coverage.record('reached',self.rules[5],source.meta_tick)
        if self.consumers.keys()==PATHS.keys():
            self.check(self.original_metadata,tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(self.original)).items()),
                'old source metadata stays immutable across migration and replay')
            self.check_originals()
            for rule in self.rules:self.coverage.record('checked',rule,source.meta_tick)
            for previous in (*self.original_sources(),*self.before.values()):self.pipeline.retire_source(previous.meta_tick)
            self.closed=True

    def check_originals(self):
        """Additional saved owners may extend the immutable-source obligation."""

    def original_sources(self):return (self.original,)

    def finish(self):
        self.check(True,self.closed,'both ownership timelines, full effect and every consumer are mandatory')
        self.coverage.finish()
