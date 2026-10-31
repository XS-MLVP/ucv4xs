"""Complete branch identity/version obligations, independently owned by sources."""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode
from suites.frontend.bpu.bpu.coverage.main_rewrite import RULES
from suites.frontend.bpu.bpu.model.main_rewrite import PC,POSITION,TARGETS,effect,direction
from suites.frontend.bpu.bpu.model.main_service import PCS,STREAM_PC,old_target,entry_plan,counter_payload,observed_counter
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.selection import middle_repair,final_repair


class MainRewriteChecks:
    alignment,bank=0,0
    observe_retention=True

    def __init__(self,pipeline,coverage):
        self.pipeline,self.coverage=pipeline,coverage
        self.failure=None;self.last=None;self.holding=False;self.pending_checked=False
        self.sources=();self.originals=();self.snapshots=();self.inputs=[];self.proposals=[];self.directions=[]
        self.accepted=();self.written=[[] for _ in range(MAIN_WAYS+1)];self.old=self.new=self.latest=None
        self.release_tick=None;self.reactivation=None;self.closed=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
            ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,request=dict(point=point,
                accepted=tuple((t,r.source.sequence,r.pc) for t,r in self.accepted),
                entry_proposals=self.proposals,direction_proposals=self.directions,
                written=self.written,release=self.release_tick,
                reactivation=None if self.reactivation is None else self.reactivation.meta_tick)))
        except Exception as error:self.failure=error;raise

    def mark(self,index,tick):self.coverage.record('reached',RULES[index],tick)

    def inspect(self,receipt,*,version=None,pc=PC):
        token=self.pipeline.source_token(receipt)
        self.check(pc,token.pc,'exact original Main record context')
        values=tuple((way,e.position,e.kind,e.counter) for way,e in enumerate(source_entries(token.lookup)[0]) if e.hit)
        self.check(((2,POSITION,1,0),(3,5,3,2)) if version is None else ((2,POSITION,3,2),(3,5,3,2)),
            values,'complete earlier record and independent later sibling')
        self.check((5,old_target(pc),3) if version is None else (POSITION,TARGETS[version],3),
            (token.middle.branch.position,token.middle.branch.target,int(token.middle.branch.kind)),
            'fresh independently selected complete branch record')
        repair2=middle_repair(token.early,token.middle)
        repair3=final_repair(token.early,token.middle,token.middle,corrected_middle=repair2)
        expected=tuple((receipt.prediction_tick+delay,stage) for delay,stage,active in ((2,2,repair2),(4,3,repair3)) if active)
        self.check(expected,self.pipeline.corrections_for_source(receipt),
            'all public correction events carry independently checked full branch outputs, not just S1 metadata')
        return token

    def arm(self,sources,originals):
        self.check((),self.sources,'one full-record rewrite program')
        self.check((2,2),(len(sources),len(originals)),'two distinct old predictions and two protected rows')
        for source in sources:self.inspect(source)
        self.check(True,sources[0].meta_tick<sources[1].prediction_tick,'different actually published original predictions')
        self.check(False,self.pipeline.source_token(sources[0]).history is self.pipeline.source_token(sources[1]).history,
            'equal PC and metadata encodings do not collapse original owners')
        for pc,source in zip(PCS,originals,strict=True):self.inspect(source,pc=pc)
        self.sources=tuple(sources);self.originals=tuple(originals)
        self.snapshots=tuple(deepcopy(source_entries(self.pipeline.source_token(s).lookup)) for s in (*sources,*originals))
        self.mark(0,sources[-1].meta_tick)

    def start(self,loop):
        token=self.pipeline.source_token(loop)
        self.check((STREAM_PC,'micro',STREAM_PC),(token.pc,token.early.source,token.early.branch.target),
            'normal early loop creates real read priority, not an artificial busy pin')
        self.holding=True

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last=event.tick,row
            self.check((0,1),(row['reset'],row['initialized']),'ordinary non-reset service window')
            if self.holding:
                self.check((1,(0,)*5),(row['read']['valid'],tuple(p['ready'] for p in row['writes'])),
                    'continuous real reads deny all entry/direction services')
                if row['training']['valid'] and row['training']['ready']:
                    p=row['prediction'];self.check((1,1),(p['valid'],p['ready']),'actual prediction overlaps each accepted input')
                    self.inputs.append(event.tick)
            for way,p in enumerate(row['incoming']):
                if p['valid']:
                    index=len(self.proposals)
                    self.check(True,index<3 and (self.holding if index<2 else self.reactivation is not None),
                        'only declared complete versions may enter')
                    self.check((2,effect(TARGETS[index])),(way,p['bits']),'full corrected type, identity, carry and target')
                    if index==1:self.check(self.proposals[0][0]+2,event.tick,'adjacent full entry versions')
                    self.proposals.append((event.tick,deepcopy(p['bits'])))
            if row['direction']['valid']:
                index=len(self.directions)
                self.check(True,index<3 and (self.holding if index<2 else self.reactivation is not None),
                    'one independent direction reset per declared correction')
                self.check((1,direction()),(row['direction']['ready'],observed_counter(row['direction']['bits'])),
                    'direction FIFO neither coalesces source effects nor changes the sibling')
                self.directions.append((event.tick,deepcopy(observed_counter(row['direction']['bits']))))
            if self.pending_checked and self.holding:self.blocked(row)
        except Exception as error:self.failure=error

    def accepted_burst(self,events):
        self.check((),self.accepted,'one genuine adjacent version burst');self.check(2,len(events),'both actual originals accepted')
        for i,(source,(tick,r)) in enumerate(zip(self.sources,events,strict=True)):
            token=self.pipeline.source_token(source)
            self.check(True,tick>source.meta_tick and r.origin is token,'correction belongs to exact frozen source')
            self.check((PC,((POSITION,TARGETS[i],3,True,True),)),(r.pc,
                tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict) for b in r.branches if b is not None)),
                'misclassified earlier conditional resolves as a real taken indirect branch')
        self.check(events[0][0]+2,events[1][0],'adjacent actual public input receipts')
        self.check(tuple(t for t,_ in events),tuple(self.inputs),'driver receipts and actual accepts agree')
        self.accepted=tuple(events);self.mark(1,events[-1][0])

    def blocked(self,row):
        self.check(dict(valid=1,ready=0,bits=effect(TARGETS[1])),row['writes'][2],
            'pending head owns only the newest COMPLETE branch version')
        self.check(((0,0),)*3,tuple((row['writes'][w]['valid'],row['writes'][w]['ready']) for w in (0,1,3)),'all unselected ways including later sibling have no entry update')
        d=row['writes'][MAIN_WAYS]
        self.check((1,0,direction()),(d['valid'],d['ready'],observed_counter(d['bits'])),
            'direction front remains independent of latest-only entry service')
        self.check(1,sum(sum(r) for r in row['dirty']),'one retained record, not two stale target versions')
        q=row['queue'];occupancy=4 if q['full'] else (q['enqueue']-q['dequeue'])%4
        self.check(2,occupancy,'both accepted direction effects survive in FIFO')

    def pending(self):
        main=self.pipeline.model.sources.main
        self.check(False,self.pending_checked,'one mature pending-version boundary')
        self.check((None,False),(main.offered,any(main.entry_offers.values())),'all original learning matured')
        self.check(((),(),(effect(TARGETS[1]),),()),entry_plan(main,0,0),'logical identity retains newest version on original owner')
        self.check((direction(),direction()),tuple(counter_payload(p) for p in main.directions[0,0].pending),
            'direction updates are not superseded with entry versions')
        self.check((0,0),(main.entries[0,0].overflows,main.directions[0,0].drops),'no capacity-loss waiver')
        self.check(tuple(effect(t) for t in TARGETS[:2]),tuple(p for _,p in self.proposals),'both full actual proposals compared')
        self.check(tuple(t+2 for t,_ in self.accepted),tuple(t for t,_ in self.proposals),'registered entry visibility boundary')
        self.check(tuple(t for t,_ in self.accepted),tuple(t for t,_ in self.directions),'direct direction acceptance boundary')
        self.check([[] for _ in range(MAIN_WAYS+1)],self.written,'neither superseded nor current version has serviced')
        self.blocked(self.last[1]);self.pending_checked=True;self.mark(2,self.last[0])

    def consumed_old(self,receipt):
        self.inspect(receipt)
        self.check(True,self.pending_checked and self.holding,'actual old consumer before release')
        self.check(True,receipt.prediction_tick>self.accepted[-1][0],'new request, not an old queued response')
        self.blocked(self.last[1]);self.check([[] for _ in range(MAIN_WAYS+1)],self.written,'old visibility precedes ALL actual service')
        self.old=receipt;self.mark(3,receipt.meta_tick)

    def release(self):
        self.check(True,self.old is not None,'fresh old consumer precedes release')
        self.check(None,self.release_tick,'single blocked-window release')
        self.release_tick=self.pipeline.last_tick;self.holding=False

    def write_accepted(self,port,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,'no service under blocked reads')
        self.check(True,port in (2,4),'no sibling entry service')
        index=len(self.written[port]);expected=(effect(TARGETS[1]),effect(TARGETS[2])) if port==2 else (direction(),)*3
        self.check(True,index<len(expected) and (index<(1 if port==2 else 2) or self.reactivation is not None),
            'no stale intermediate, duplicate or undeclared service')
        actual=transfer.value if port==2 else observed_counter(transfer.value)
        self.check(expected[index],actual,'SDK-confirmed complete version service, not just a valid pulse')
        self.written[port].append((transfer.accepted_tick,deepcopy(actual)))
        if tuple(map(len,self.written))==(0,0,1,0,2):self.mark(4,transfer.accepted_tick)

    def consumed_new(self,receipt):
        self.check((0,0,1,0,2),tuple(map(len,self.written)),'latest-only entry and both directions precede fresh consumer')
        self.inspect(receipt,version=1)
        self.check(True,receipt.prediction_tick>max(t for w in self.written for t,_ in w),'fresh committed latest-version read')
        self.check(((),)*4,entry_plan(self.pipeline.model.sources.main,0,0),'latest record is now clean')
        self.new=receipt;self.mark(5,receipt.meta_tick)

    def reactivate(self,receipt):
        self.check(True,self.new is receipt,'clean reactivation uses the exact freshly verified current owner')
        self.check(None,self.reactivation,'one new clean version')
        self.inspect(receipt,version=1);self.reactivation=receipt

    def consumed_latest(self,receipt):
        self.check((0,0,2,0,3),tuple(map(len,self.written)),'new clean version actually serviced once with its own direction')
        self.inspect(receipt,version=2)
        self.check(True,receipt.prediction_tick>max(t for w in self.written for t,_ in w),'fresh post-reactivation full-target read')
        self.latest=receipt;self.mark(6,receipt.meta_tick)

    def finish(self,sibling):
        self.check(False,self.closed,'single closure')
        self.check(True,self.old is not None and self.new is not None and self.latest is not None,'all three visibility endpoints observed')
        self.inspect(sibling,pc=PCS[1])
        self.check(self.snapshots,tuple(source_entries(self.pipeline.source_token(s).lookup) for s in (*self.sources,*self.originals)),
            'all original same-PC and other-row metadata remains immutable')
        self.check(False,self.pipeline.model.sources.main_pending(),'all own effects have drained')
        self.check((0,)*5,tuple(w['valid'] for w in self.last[1]['writes']),'no extra unconsumed actual service')
        self.mark(7,sibling.meta_tick)
        for rule in RULES:self.coverage.record('checked',rule,sibling.meta_tick)
        self.coverage.finish();self.closed=True
        for source in {s.meta_tick:s for s in (*self.sources,*self.originals,self.old,self.new,self.latest,sibling)}.values():
            self.pipeline.retire_source(source.meta_tick)
