"""A complete target patch needs retention, actual service and a new consumer."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode

from suites.frontend.bpu.bpu.coverage.indirect_service import RULES
from suites.frontend.bpu.bpu.model.ittage_service import PC,POSITION,TARGETS,payload,pending_plan,offered_payload
from suites.frontend.bpu.ittage.model.semantic import coordinates


class IndirectServiceChecks:
    observe_retention=True

    def __init__(self,pipeline,coverage,table):
        self.pipeline,self.coverage,self.table=pipeline,coverage,table;self.bank=PC%2
        self.failure=None;self.sources=();self.metadata=();self.contexts=();self.plan=()
        self.accepted=();self.input_ticks=[];self.proposals=[];self.written=[]
        self.holding=False;self.pending_checked=False;self.last=None;self.release_tick=None
        self.old_sources={};self.new_sources={};self.closed=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
            ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,
            request=dict(point=point,table=self.table,accepted=self.accepted,written=self.written)))
        except Exception as error:self.failure=error;raise

    def source(self,receipt):
        token=self.pipeline.source_token(receipt)
        self.check(PC,token.pc,'every tracked target belongs to the same indirect instruction')
        return token,self.pipeline.model.sources.snapshot(token,resolved=True)

    def target(self,receipt,index,confidence):
        token,source=self.source(receipt);prediction=source.prediction
        self.check(True,prediction is not None and source.read is not None and source.late is not None,
            'a fully resolved independent source precedes target inspection')
        self.check((self.table,None,confidence,0,TARGETS[index]*2),
            (prediction.provider,prediction.alternate,prediction.confidence,prediction.useful,prediction.target),
            'independent original context, confidence and complete foreign-region target')
        self.check((POSITION,TARGETS[index],True,3,'indirect-history'),
            (source.late.branch.position,source.late.branch.target,source.late.branch.taken,int(source.late.branch.kind),source.late.source),
            'exact final indirect target from the owned source')
        return token,source

    def arm(self,sources):
        self.check((),self.sources,'one four-context service experiment')
        self.check(4,len(sources),'four distinct original predictions before feedback')
        tokens=[];reads=[]
        for index,receipt in enumerate(sources):
            token,source=self.target(receipt,index,2);tokens.append(token);reads.append(source.read)
            if index:self.check(True,sources[index-1].meta_tick<receipt.prediction_tick,'distinct ordered original accepts')
        self.check(4,len({id(t.history) for t in tokens}),'four original checkpoint owners')
        self.contexts=tuple(read.context for read in reads)
        self.check(4,len(set(self.contexts)),'four real history contexts')
        rows=tuple(coordinates(PC*2,context,self.table)[1] for context in self.contexts)
        self.check(4,len(set(rows)),'four independent row obligations, not alias labels')
        self.check((0,1,2,3),tuple(read.entries[self.table].target.pointer for read in reads),
            'four independently allocated foreign-region identities')
        self.sources=tuple(sources)
        self.metadata=tuple(deepcopy(self.pipeline.model.sources.defined_ittage_metadata(token)) for token in tokens)
        self.plan=tuple(payload(row,read.entries[self.table],confidence=3) for row,read in zip(rows,reads,strict=True))

    def begin_read_window(self):
        self.check(4,len(self.sources),'all original predictions qualified before streaming')
        self.check(False,self.holding,'one continuous read window');self.holding=True

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last=event.tick,row
            self.check((0,0),(row['reset'],row['maintenance']),'reset/maintenance cannot replace ordinary pending effects')
            if self.holding:
                read=row['read'];self.check((1,1,self.bank),(read['valid'],read['ready'],read['pc']%2),'uninterrupted same-bank SRAM reads')
                self.check(0,row['write']['ready'],'read priority denies actual target service')
                if row['training']['valid'] and row['training']['ready']:
                    prediction=row['prediction']
                    self.check((1,1,self.bank),(prediction['valid'],prediction['ready'],prediction['pc']%2),
                        'a real prediction accepts beside every feedback input')
                    self.input_ticks.append(event.tick)
            if row['incoming']['valid']:
                self.check(True,self.holding and not self.pending_checked,'ordinary effects enter only the declared blocked phase')
                index=len(self.proposals);self.check(True,index<4,'no extra or duplicate target proposal')
                self.check(offered_payload(self.plan[index]),row['incoming']['bits'],'complete offered target patch and context order')
                if index:self.check(self.proposals[-1][0]+2,event.tick,'all four target proposals are adjacent')
                self.proposals.append((event.tick,deepcopy(row['incoming']['bits'])))
            if self.pending_checked and self.holding:self.blocked(row)
        except Exception as error:self.failure=error

    def accepted_burst(self,events):
        self.check((),self.accepted,'one actual four-source burst');self.check(4,len(events),'every original input accepted')
        for index,(receipt,(tick,resolution)) in enumerate(zip(self.sources,events,strict=True)):
            token,source=self.source(receipt)
            self.check(True,tick>receipt.meta_tick and resolution.origin is token,'accepted input has the exact original owner')
            self.check((PC,((POSITION,TARGETS[index],3,True,False,0),)),
                (resolution.pc,tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict,int(b.action))
                    for b in resolution.branches if b is not None)),'complete correct indirect feedback, not invented mispredictions')
            self.check(TARGETS[index],source.late.branch.target,'correctness follows the independently predicted original target')
            if index:self.check(events[index-1][0]+2,tick,'adjacent actual driver accepts')
        self.check(tuple(tick for tick,_ in events),tuple(self.input_ticks),'monitored public accepts equal owned driver receipts')
        control=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(control[0],bool(control[1][2] and control[1][5])),'Main/ITTAGE genuinely enabled')
        self.accepted=tuple(events);self.coverage.record('reached',RULES[0],events[-1][0])

    def blocked(self,row):
        self.check(dict(valid=1,ready=0,bits=self.plan[0]),row['write'],'oldest complete target remains blocked and stable')
        self.check((1,1,1,1),row['dirty'],'all four actual pending slots retain obligations')

    def pending(self):
        self.check(False,self.pending_checked,'one mature pending boundary')
        self.check(4,len(self.accepted),'actual inputs precede pending effects')
        model=self.pipeline.model.sources.indirect
        self.check((None,()),(model.learning,model.normal),'learning has matured before retention is judged')
        self.check(self.plan,pending_plan(model,self.table,self.bank),'all independent context effects survive in declared service order')
        self.check(0,model.caches[self.table][self.bank].overwrites,'capacity-safe program has no full-miss waiver')
        self.check(tuple(offered_payload(p) for p in self.plan),tuple(p for _,p in self.proposals),
            'all complete actual proposals compared before old consumption')
        self.check(True,all(p[0]>e[0] for p,e in zip(self.proposals,self.accepted,strict=True)),'effect follows its own accepted input')
        self.check([],self.written,'no hidden commit under continuous reads')
        self.check(self.pipeline.last_tick,self.last[0],'independent and actual pending states share one boundary')
        self.blocked(self.last[1]);self.pending_checked=True;self.coverage.record('reached',RULES[1],self.last[0])

    def consumed(self,receipt,index,*,committed):
        self.check(True,index in range(4),'only declared history identities')
        token,source=self.target(receipt,index,3 if committed else 2)
        self.check(self.contexts[index],source.read.context,'new read has the original complete folded history')
        self.check(True,receipt.prediction_tick>(self.written[-1][0] if committed and self.written else self.accepted[-1][0]),
            'consumer is a new post-input/post-commit request')
        expected=((receipt.prediction_tick+2,2),)+(((receipt.prediction_tick+4,3),) if TARGETS[index]!=TARGETS[-1] else ())
        self.check(expected,self.pipeline.corrections_for_source(receipt),'complete final target repair window for this history')
        destination=self.new_sources if committed else self.old_sources
        self.check(False,index in destination,'one fresh consumer per original history per visibility boundary')
        if not committed:
            self.check(True,self.pending_checked and self.holding,'old visibility must be checked before read release')
            self.check([],self.written,'no SRAM service before all old consumers');self.blocked(self.last[1])
        else:
            self.check(4,len(self.written),'all actual target commits precede committed consumption')
            self.check((),pending_plan(self.pipeline.model.sources.indirect,self.table,self.bank),'every independent target effect drained')
            self.check(0,self.last[1]['write']['valid'],'no unconsumed extra actual target write')
        destination[index]=receipt
        if len(destination)==4:self.coverage.record('reached',RULES[4 if committed else 2],receipt.meta_tick)

    def release(self):
        self.check(4,len(self.old_sources),'every original history sees old confidence before read release')
        self.check(None,self.release_tick,'one read release');self.release_tick=self.pipeline.last_tick;self.holding=False

    def write_accepted(self,port,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,'actual service follows declared release')
        self.check(0,port,'one service port for this bank')
        index=len(self.written);self.check(True,index<4,'one complete service for every context')
        self.check(self.plan[index],transfer.value,'SDK-confirmed full payload and target service order')
        self.written.append((transfer.accepted_tick,deepcopy(transfer.value)))
        if len(self.written)==4:self.coverage.record('reached',RULES[3],transfer.accepted_tick)

    def finish(self):
        self.check((4,4,4,4),(len(self.accepted),len(self.old_sources),len(self.written),len(self.new_sources)),
            'all inputs, old consumers, actual commits and new consumers')
        current=tuple(self.pipeline.model.sources.defined_ittage_metadata(self.pipeline.source_token(s)) for s in self.sources)
        self.check(self.metadata,current,'original source snapshots remain immutable')
        # Every foreign region remains owned; decoding must not silently fall back to PC region.
        regions=self.pipeline.model.sources.indirect.regions.regions
        self.check(tuple(target*2>>20 for target in TARGETS),tuple(regions[:4]),'all four independently learned foreign regions preserved')
        tick=max(s.meta_tick for s in self.new_sources.values());self.coverage.record('reached',RULES[5],tick)
        for rule in RULES:self.coverage.record('checked',rule,tick)
        self.coverage.finish()
        for receipt in (*self.sources,*self.old_sources.values(),*self.new_sources.values()):self.pipeline.retire_source(receipt.meta_tick)
        self.closed=True
