"""Exact read ancestors, actual allocation and two independently checked consumers."""
from copy import deepcopy
from dataclasses import asdict
from bpuverify.bpu.checker.entry_protection import Checks as ProtectionChecks
from bpuverify.bpu.model.short_revisit import program,rules,EXTRA
from bpuverify.bpu.model.early_opposition import provider,resident
from bpuverify.bpu.model.path_history import WIDTH,SHIFT,path_contribution
from bpuverify.utage.model.semantic import Entry,HISTORIES,tag


class Checks(ProtectionChecks):
    def __init__(self,coverage,profile):
        self.revisit=program(profile); self.metadata={}
        super().__init__(coverage,self.revisit.base_name)
        self.completion_rules=rules(profile)
        self.bridge_source=None; self.bridge=None; self.pending_long=None; self.long_allocations={}
        self.long=None; self.short=None; self.long_source=None; self.short_source=None; self.path=[]; self.before_path=None

    def save(self,source):
        token=super().save(source)
        self.metadata.setdefault(source.meta_tick,(source,deepcopy(getattr(source,'meta',None))))
        self.check(True,self.pipeline.model.published.get(token.sequence) is token,'published original, never an equal copied source')
        return token

    def before_flowing_recovery(self,source):
        self.check(None,self.bridge_source,'one declared original read ancestor')
        token=self.save(source); self.bridge_source=source
        self.bridge=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            history=token.history.history,taken_edges=token.history.taken_edges)
        self.mark(EXTRA[0],source.meta_tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        self.confirming_long=self.pending_long
        return super().candidates(row,events,cycle,model,phase,previous)

    def checked(self,tick,*candidates):
        super().checked(tick,*candidates)
        if self.confirming_long is not None:
            row=self.confirming_long
            self.check(row['written_tick']+2,tick,'new long allocation crosses next full actual comparison')
            self.check(2,self.actual_useful[1][row['index']],'actual long protection initialized independently')
            self.long_allocations[row['owner']]=dict(row,actual_confirmation_tick=tick)
            self.mark(EXTRA[1],tick); self.mark(EXTRA[2],tick)
        self.pending_long=None
        if self.applied is None or self.bridge_source is None: return
        owner=next((t for f,t in self.offers if f is self.applied.feedback),None)
        if owner is None: return
        value=provider(self.pipeline.model.sources,owner)
        if value is None or value.key!=self.protected or value.counter>=4: return
        for table,index,before,after,role in self.pipeline.model.sources.short.effects:
            if table!=1 or role!='allocate': continue
            feedback=self.applied.feedback; intended=tag(feedback.pc,feedback.context,1)
            self.check((2,True,1,0),(feedback.position,feedback.taken,feedback.kind,self.applied.useful[1]),
                'new long entry comes from the same wrong short original and common eligible prestate')
            self.check(Entry(True,intended,2,4),resident(self.pipeline.model.sources,(1,index)),
                'independent long allocation direction, identity and initial confidence')
            self.pending_long=dict(owner=owner.sequence,index=index,tag=intended,position=2,counter=4,
                before=before,after=after,common_read_before=self.applied.useful[1],written_tick=tick)

    def allocation_for_wrong(self):
        self.check(True,self.wrong is not None and self.wrong['owner'] in self.long_allocations,'named wrong short owns confirmed new long entry')
        return self.long_allocations[self.wrong['owner']]

    def long_consumer(self,source):
        token=self.save(source); value=provider(self.pipeline.model.sources,token)
        allocation=self.allocation_for_wrong()
        self.check(True,value is not None,'fresh long consumer is actually qualified')
        self.check((1,allocation['index'],allocation['tag'],2,4),(value.table,value.index,value.tag,value.position,value.counter),
            'fresh public consumer reads the actual new long identity and T4, not another long hit')
        self.check(True,source.prediction_tick>allocation['actual_confirmation_tick'],'new long request follows actual allocation')
        bridge=self.save(self.bridge_source)
        self.check(True,self.last_redirect is not None and self.last_redirect[1] is bridge.history,
            'same actual read ancestor, not the wrong S3 source or a numerically equal checkpoint')
        frame=self.pipeline.model.sources.short_snapshot(token).prediction.frame
        short=frame.read.entries[0]
        self.check((self.protected[1],self.protected_entry.tag,2,1),
            (frame.read.indices[0],short.tag,short.position,short.counter),'short candidate still exists beneath long priority')
        self.check(True,short.valid and short.tag==tag(frame.pc,frame.context,0),'long selected when the original short also matches')
        self.long=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),allocation=allocation,short_candidate=asdict(short),read_ancestor_owner=bridge.sequence)
        self.long_source=source
        self.mark(EXTRA[3],source.meta_tick)

    def begin_path(self):
        sources=self.pipeline.model.sources; short=resident(sources,self.protected)
        self.check(1,short.counter,'long learning has not overwritten short error update')
        self.before_path=short,sources.short.useful[0].get(self.protected[1],0)

    def path_receipt(self,before,position,after):
        self.check(True,self.before_path is not None,'path begins after qualified long consumer')
        self.check(self.revisit.positions[len(self.path)],position,'predeclared older edge and common recent suffix')
        old=self.save(before); new=self.save(after)
        expected=((old.history.history<<SHIFT)^path_contribution((self.pc//8)*8+position,self.pc))%(1<<WIDTH)
        self.check((expected,old.history.taken_edges+1),(new.history.history,new.history.taken_edges),'complete new original checkpoint for one semantic path edge')
        self.check(True,after.prediction_tick>before.meta_tick,'path edge has a new complete public original')
        self.path.append(dict(before_owner=old.sequence,owner=new.sequence,position=position,
            history=new.history.history,taken_edges=new.history.taken_edges,prediction_tick=after.prediction_tick,meta_tick=after.meta_tick))

    def path_ready(self):
        self.check(self.revisit.positions,tuple(r['position'] for r in self.path),'entire declared prefix and recent suffix')
        sources=self.pipeline.model.sources
        self.check(self.before_path,(resident(sources,self.protected),sources.short.useful[0].get(self.protected[1],0)),
            'all frozen short data and protection survive other path preparation')
        self.mark(EXTRA[4],self.path[-1]['meta_tick']); self.mark(EXTRA[5],self.path[-1]['meta_tick'])

    def short_consumer(self,source):
        token=self.save(source); value=provider(self.pipeline.model.sources,token)
        self.check(True,value is not None,'fresh original short consumer, not just a correct Main prediction')
        self.check((0,self.protected[1],self.protected_entry.tag,2,1),
            (value.table,value.index,value.tag,value.position,value.counter),'fresh NT1 consumes the retained original short error result')
        frame=self.pipeline.model.sources.short_snapshot(token).prediction.frame
        long=frame.read.entries[1]
        self.check(False,long.valid and long.tag==tag(frame.pc,frame.context,1) and long.position==2,
            'new older path truly does not match the longer provider; long table remains enabled')
        original=self.pipeline.source_token(self.wrong_source)
        self.check(token.history.history% (1<<HISTORIES[0]),original.history.history% (1<<HISTORIES[0]),'same recent path identity')
        self.check(True,token.history.history% (1<<HISTORIES[1])!=original.history.history% (1<<HISTORIES[1]),'older path differs within the actual longer-history width')
        self.check(True,source.prediction_tick>self.long['meta_tick'],'short request follows actual long consumption')
        self.short=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),history=token.history.history,read_indices=frame.read.indices)
        self.short_source=source
        self.mark(EXTRA[6],source.meta_tick); self.mark(EXTRA[7],source.meta_tick)
        self.final_source(source)

    def finish_opposition(self,additional_sources=(),*,completion_tick=None):
        self.check(True,self.bridge is not None and self.long is not None and self.short is not None,'exact read ancestor and both consumers required')
        self.check(None,self.pending_long,'no unconfirmed long allocation')
        self.check(self.revisit.positions,tuple(r['position'] for r in self.path),'no omitted path edge')
        bridge=self.save(self.bridge_source)
        self.check(bridge.sequence,self.long['read_ancestor_owner'],'long consumer retains exact read ancestor')
        self.check(self.allocation_for_wrong(),self.long['allocation'],'long consumer keeps its confirmed allocation receipt')
        self.check(self.long['provider'],asdict(provider(self.pipeline.model.sources,self.save(self.long_source))),'long consumer snapshot cannot be rebound')
        self.check(self.short['provider'],asdict(provider(self.pipeline.model.sources,self.save(self.short_source))),'short consumer snapshot cannot be rebound')
        for source,meta in self.metadata.values():
            self.check(meta,getattr(source,'meta',None),'original public metadata is immutable across both learning lifetimes')
        self.mark(EXTRA[8],self.short['meta_tick'])
        super().finish_opposition(additional_sources,completion_tick=self.short['meta_tick'])

    def snapshot(self):
        result=super().snapshot()
        result.update(profile=self.revisit.name,bridge=self.bridge,long=self.long,short=self.short,path=self.path,
            long_allocations=self.long_allocations,new_short_direction_consumer_proved=self.closed and self.short is not None,
            new_long_allocation_consumer_proved=self.closed and self.long is not None)
        return result
