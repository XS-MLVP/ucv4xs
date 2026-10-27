"""Entry owner, masked direction owner and visibility must agree independently."""
from copy import deepcopy
from toffee import CheckContext,ScoreboardMode
from bpuverify.bpu.coverage.main_service import main_service_rules
from bpuverify.bpu.model.main_service import PCS,POSITION,PEER_POSITION,STREAM_PC,old_target,new_target,target_effect,reclassification_effect,after_earlier_branch,entry_plan,counter_payload,observed_counter
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.selection import middle_repair,final_repair
from bpuverify.mbtb.model.semantic import coordinate,replacement_row,Entry,Target,tag,Write


class MainServiceChecks:
    observe_retention=True
    alignment,bank=0,0

    def __init__(self,pipeline,coverage,*,stale=False,reclassify=False):
        if stale and reclassify:raise ValueError('stale-owner and current-source reclassification are separate profiles')
        self.pipeline,self.coverage,self.stale,self.reclassify=pipeline,coverage,stale,reclassify
        self.rules=main_service_rules('reclassification' if reclassify else 'retained-owner' if stale else 'service')
        self.owner=0 if reclassify else 1
        self.pcs=PCS[-1:] if stale else PCS
        self.sources=();self.originals=();self.snapshots=();self.failure=None
        effects=tuple((reclassification_effect if reclassify else target_effect)(pc) for pc in self.pcs)
        self.plan=(effects,()) if reclassify else ((),effects)
        self.counter_plan=tuple(dict(row=coordinate(pc)[2],mask=1 if reclassify else 2 if stale else 3,
            values={'0':2} if reclassify else {'1':2} if stale else {'0':0,'1':2}) for pc in self.pcs)
        self.inputs=[];self.proposals=[];self.counter_proposals=[];self.accepted=()
        self.written=[[],[],[]];self.old={};self.new={};self.siblings={};self.holding=False;self.pending_checked=False
        self.release_tick=None;self.last=None;self.closed=False

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
            ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,
            request=dict(point=point,stale=self.stale,pcs=self.pcs,accepted=self.accepted,written=self.written,
                entry_proposals=self.proposals,direction_proposals=self.counter_proposals)))
        except Exception as error:self.failure=error;raise

    @property
    def service_shape(self):
        return tuple(len(self.pcs) if port in (self.owner,2) else 0 for port in range(3))

    def inspect(self,receipt,pc,target,*,committed=False):
        token=self.pipeline.source_token(receipt)
        self.check(pc,token.pc,'exact real Main read PC')
        entries=tuple((way,e.position,e.kind,e.counter) for way,e in enumerate(source_entries(token.lookup)[0]) if e.hit)
        changed=self.reclassify and committed
        self.check(((0,PEER_POSITION,3 if changed else 1,2 if changed else 0),(1,POSITION,3,2)),entries,
            'complete reclassified earlier record or negative peer, and independent later indirect')
        self.check((PEER_POSITION if changed else POSITION,target,True,3),(token.middle.branch.position,token.middle.branch.target,
            token.middle.branch.taken,int(token.middle.branch.kind)),'complete independently selected Main target')
        return token

    def arm(self,sources,originals):
        self.check((),self.sources,'one declared Main service program');self.check(len(self.pcs),len(sources),'all original inputs')
        self.check(2,len(originals),'both complete prepared rows are protected')
        for pc,source in zip(PCS,originals,strict=True):self.inspect(source,pc,old_target(pc))
        for i,(pc,source) in enumerate(zip(self.pcs,sources,strict=True)):
            token=self.pipeline.source_token(source)
            if self.stale:
                self.check(False,any(e.hit for row in source_entries(token.lookup) for e in row),'actual old cold metadata was captured before learning')
                self.check(False,token.early.branch.taken,'cold original genuinely predicted fallthrough')
                main=self.pipeline.model.sources.main;entry=Entry(tag(pc),POSITION,3,0,Target.encode(pc,new_target(pc)))
                self.check((0,1),(main.recency[0,replacement_row(pc)],main.entries[0,0].owner(Write(coordinate(pc)[2],0,entry))),
                    'old nomination is peer0 but retained logical entry still belongs to owner1')
            else:self.inspect(source,pc,old_target(pc))
            if i:self.check(True,sources[i-1].meta_tick<source.prediction_tick,'independent ordered original predictions')
        self.sources=tuple(sources);self.originals=tuple(originals)
        self.snapshots=tuple(source_entries(self.pipeline.source_token(s).lookup) for s in (*self.sources,*self.originals))

    def start(self,loop):
        self.check(False,self.holding,'one continuous Main read window')
        token=self.pipeline.source_token(loop)
        self.check((STREAM_PC,STREAM_PC,True,'micro'),(token.pc,token.early.branch.target,token.early.branch.taken,token.early.source),
            'normally learned early self-loop sustains same-bank predictions')
        self.holding=True

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last=event.tick,row;self.check((0,1),(row['reset'],row['initialized']),'ordinary learning, not reset service')
            if self.holding:
                self.check(1,row['read']['valid'],'uninterrupted actual Main-bank reads')
                self.check((0,0,0),tuple(w['ready'] for w in row['writes']),'entry and direction service both denied by reads')
                if row['training']['valid'] and row['training']['ready']:
                    p=row['prediction'];self.check((1,1,0),(p['valid'],p['ready'],coordinate(p['pc'])[1]),'real prediction beside each actual feedback')
                    self.inputs.append(event.tick)
            for way,p in enumerate(row['incoming']):
                if p['valid']:
                    index=len(self.proposals);self.check(True,self.holding and not self.pending_checked and index<len(self.pcs),'one ordinary complete effect per declared source')
                    self.check((0 if self.stale else self.owner,self.plan[self.owner][index]),(way,p['bits']),'offered entry may nominate another way, never another target')
                    if index:self.check(self.proposals[-1][0]+2,event.tick,'adjacent complete entry effects')
                    self.proposals.append((event.tick,way,deepcopy(p['bits'])))
            if row['direction']['valid']:
                index=len(self.counter_proposals);self.check(True,self.holding and index<len(self.pcs),'one defined direction effect per original source')
                self.check(1,row['direction']['ready'],'capacity-safe program must not drop direction effects')
                self.check(self.counter_plan[index],observed_counter(row['direction']['bits']),
                    'direction reset belongs to the retained record; the unrelated sibling is not reset')
                if index:self.check(self.counter_proposals[-1][0]+2,event.tick,'adjacent masked direction effects')
                self.counter_proposals.append((event.tick,deepcopy(observed_counter(row['direction']['bits']))))
            if self.pending_checked and self.holding:self.blocked(row)
        except Exception as error:self.failure=error

    def accepted_burst(self,events):
        self.check((),self.accepted,'one original burst');self.check(len(self.pcs),len(events),'every source really accepted')
        for i,(source,pc,(tick,r)) in enumerate(zip(self.sources,self.pcs,events,strict=True)):
            token=self.pipeline.source_token(source)
            self.check(True,tick>source.meta_tick and r.origin is token,'exact old owner precedes actual acceptance')
            expected=((PEER_POSITION,new_target(pc),3,True,True),) if self.reclassify else ((POSITION,new_target(pc),3,True,True),) if self.stale else (
                (PEER_POSITION,pc+0x200,1,False,False),(POSITION,new_target(pc),3,True,True))
            self.check((pc,expected),(r.pc,tuple((b.position,b.target,int(b.kind),b.taken,b.mispredict) for b in r.branches if b is not None)),
                'complete genuine target correction, with matching negative prefix when tracked')
            if i:self.check(events[i-1][0]+2,tick,'adjacent actual public inputs')
        self.check(tuple(t for t,_ in events),tuple(self.inputs),'monitored public accepts equal driver-owned receipts')
        control=self.pipeline.last_resolution_controls
        self.check((events[-1][0],True),(control[0],bool(control[1][0] and control[1][2])),'Micro/Main really enabled')
        self.accepted=tuple(events);self.coverage.record('reached',self.rules[0],events[-1][0])

    def blocked(self,row):
        self.check(0,row['writes'][1-self.owner]['valid'],'unrelated entry owner has no target service')
        self.check(dict(valid=1,ready=0,bits=self.plan[self.owner][0]),row['writes'][self.owner],'oldest complete target remains blocked')
        actual=row['writes'][2];self.check((1,0,self.counter_plan[0]),(actual['valid'],actual['ready'],observed_counter(actual['bits'])),
            'separate masked direction obligation remains blocked')
        self.check(len(self.pcs),sum(sum(r) for r in row['dirty']),'every target obligation occupies a real retained slot')
        q=row['queue'];occupancy=(2 if q['full'] else 0) if q['enqueue']==q['dequeue'] else 1
        self.check(len(self.pcs),occupancy,'all masked direction obligations survive in their separate finite FIFO')

    def pending(self):
        main=self.pipeline.model.sources.main
        self.check(False,self.pending_checked,'one mature retention boundary')
        self.check(len(self.pcs),len(self.accepted),'actual original accepts precede obligations')
        self.check((None,False),(main.offered,any(main.entry_offers.values())),'ordinary learning matured before retention judgment')
        self.check(self.plan,entry_plan(main,0,0),'independent complete target service sequence')
        self.check(self.counter_plan,tuple(counter_payload(p) for p in main.directions[0,0].pending),'independent masked direction service sequence')
        self.check((0,0),(main.entries[0,0].overflows,main.directions[0,0].drops),'no full-miss or FIFO-loss waiver')
        self.check(self.plan[self.owner],tuple(p for _,_,p in self.proposals),'all complete actual entry proposals compared')
        self.check(self.counter_plan,tuple(p for _,p in self.counter_proposals),'all actual counter proposals compared')
        # Rising snapshots see the combinational t1 direction enqueue at the
        # accepted-input boundary. Entry's additional RegNext is visible one
        # cycle later. Neither offered boundary is an SRAM commit.
        self.check(tuple(t+2 for t,_ in self.accepted),tuple(p[0] for p in self.proposals),
            'entry offer has its additional one-cycle register, not a guessed settling wait')
        self.check(tuple(t for t,_ in self.accepted),tuple(p[0] for p in self.counter_proposals),
            'direct t1 direction enqueue shares the original accepted-input sample boundary')
        self.check([[],[],[]],self.written,'no earlier actual commit')
        self.check(self.pipeline.last_tick,self.last[0],'owned and actual retention share one boundary')
        self.blocked(self.last[1]);self.pending_checked=True;self.coverage.record('reached',self.rules[1],self.last[0])

    def consumed(self,source,index,*,committed):
        self.check(True,index in range(len(self.pcs)),'only declared source contexts')
        pc=self.pcs[index];self.inspect(source,pc,new_target(pc) if committed else old_target(pc),committed=committed)
        if committed:self.check(self.service_shape,tuple(map(len,self.written)),
            'all entry and direction services precede committed consumption')
        self.check(True,source.prediction_tick>(max(t for w in self.written for t,_ in w) if committed else self.accepted[-1][0]),
            'each consumer is a fresh post-input or post-service request')
        token=self.pipeline.source_token(source);r2=middle_repair(token.early,token.middle)
        r3=final_repair(token.early,token.middle,token.middle,corrected_middle=r2)
        expected=tuple((source.prediction_tick+delay,stage) for delay,stage,active in ((2,2,r2),(4,3,r3)) if active)
        self.check(expected,self.pipeline.corrections_for_source(source),
            'structural kind/position changes and target-only changes have independently selected repair windows')
        destination=self.new if committed else self.old
        self.check(False,index in destination,'one consumer per declared context and visibility boundary')
        if not committed:
            self.check(True,self.pending_checked and self.holding,'old visibility before read release');self.blocked(self.last[1])
            self.check([[],[],[]],self.written,'no hidden service before old consumer')
        else:
            self.check(self.service_shape,tuple(map(len,self.written)),'all complete actual services precede fresh new reads')
            main=self.pipeline.model.sources.main;self.check(((),()),entry_plan(main,0,0),'no pending entry effect after service')
            self.check([],main.directions[0,0].pending,'no pending direction effect after service')
        destination[index]=source
        if len(destination)==len(self.pcs):self.coverage.record('reached',self.rules[4 if committed else 2],source.meta_tick)

    def sibling(self,source,index):
        """A fresh offset fetch makes the otherwise hidden target observable.

        The owned token is independently compared with actual stage choices,
        metadata and public source by the pipeline checker. Merely asserting
        that its unselected model entry stayed unchanged is not DUT evidence.
        """
        self.check(True,self.reclassify and index in range(len(self.pcs)),'declared reclassification sibling consumer')
        self.check(False,index in self.siblings,'one fresh sibling consumer per context')
        self.check(len(self.pcs),len(self.new),'complete rewritten consumers precede sibling protection checks')
        self.check(self.service_shape,tuple(map(len,self.written)),'all actual services precede sibling consumption')
        pc=self.pcs[index];token=self.pipeline.source_token(source)
        self.check(after_earlier_branch(pc),token.pc,'fresh fetch starts after the earlier branch')
        self.check(True,source.prediction_tick>max(s.meta_tick for s in self.new.values()),
            'sibling is a new actual request, not a prepared or hidden model record')
        self.check((POSITION,old_target(pc),True,3),(token.middle.branch.position,token.middle.branch.target,
            token.middle.branch.taken,int(token.middle.branch.kind)),
            'later sibling target is selected and independently compared, not masked by the earlier taken branch')
        entries=source_entries(token.lookup)[0]
        self.check(((PEER_POSITION,3,2),(POSITION,3,2)),tuple((e.position,e.kind,e.counter) for e in entries),
            'offset filtering preserves both record identities and counters')
        r2=middle_repair(token.early,token.middle)
        r3=final_repair(token.early,token.middle,token.middle,corrected_middle=r2)
        expected=tuple((source.prediction_tick+delay,stage) for delay,stage,active in ((2,2,r2),(4,3,r3)) if active)
        self.check(expected,self.pipeline.corrections_for_source(source),'actual offset consumer has independently derived repair windows')
        self.siblings[index]=source

    def release(self):
        self.check(len(self.pcs),len(self.old),'all old target consumers precede release')
        self.check(None,self.release_tick,'one release');self.release_tick=self.pipeline.last_tick;self.holding=False

    def write_accepted(self,port,transfer):
        self.check(True,self.release_tick is not None and transfer.accepted_tick>self.release_tick,'actual service only after declared release')
        self.check(True,port in (self.owner,2),'unrelated owner cannot silently acquire a target')
        actual=observed_counter(transfer.value) if port==2 else transfer.value
        expected=self.counter_plan if port==2 else self.plan[port];index=len(self.written[port])
        self.check(True,index<len(expected),'no extra or duplicate actual service')
        self.check(expected[index],actual,'SDK-confirmed complete payload and independent service order')
        self.written[port].append((transfer.accepted_tick,deepcopy(actual)))
        if tuple(map(len,self.written))==self.service_shape:
            self.coverage.record('reached',self.rules[3],transfer.accepted_tick)

    def finish(self):
        if self.reclassify:
            self.check(set(range(len(self.pcs))),set(self.siblings),
                'every later sibling needs a fresh selected consumer before checked credit')
        self.check((len(self.pcs),)*5,(len(self.accepted),len(self.old),len(self.written[self.owner]),len(self.written[2]),len(self.new)),
            'every accepted source has old consumption, both real services and new consumption')
        self.check((0,0,0),tuple(p['valid'] for p in self.last[1]['writes']),'no extra unconsumed actual service')
        current=tuple(source_entries(self.pipeline.source_token(s).lookup) for s in (*self.sources,*self.originals))
        self.check(self.snapshots,current,'old source metadata does not rebase after target rewrites')
        tick=max(s.meta_tick for s in self.new.values());self.coverage.record('reached',self.rules[5],tick)
        for rule in self.rules:self.coverage.record('checked',rule,tick)
        self.coverage.finish()
        for s in {r.meta_tick:r for r in (*self.sources,*self.originals,*self.old.values(),*self.new.values(),*self.siblings.values())}.values():
            self.pipeline.retire_source(s.meta_tick)
        self.closed=True
