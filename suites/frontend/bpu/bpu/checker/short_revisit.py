"""Exact read ancestors, actual allocation and two independently checked consumers."""
from copy import deepcopy
from collections import deque
from dataclasses import asdict
from suites.frontend.bpu.bpu.checker.entry_protection import Checks as ProtectionChecks
from suites.frontend.bpu.bpu.model.short_revisit import program,rules,EXTRA
from suites.frontend.bpu.bpu.model.early_opposition import provider,resident
from suites.frontend.bpu.bpu.model.path_history import WIDTH,SHIFT,path_contribution
from suites.frontend.bpu.utage.model.semantic import Entry,HISTORIES,tag,indices,Context


class Checks(ProtectionChecks):
    def __init__(self,coverage,profile):
        self.revisit=program(profile); self.metadata={}
        super().__init__(coverage,self.revisit.base_name)
        self.completion_rules=rules(profile)
        self.bridge_source=None; self.bridge=None; self.pending_long=None; self.long_allocations={}
        self.long=None; self.short=None; self.long_source=None; self.short_source=None; self.path=[]; self.before_path=None
        self.wrong_acceptance=None; self.selected_wrong=None; self.selected_wrong_tick=None; self.wrong_window=False
        self.wrong_candidates=deque(maxlen=8)
        self.first_wrong_candidates=[]
        self.wrong_precondition=None
        self.preparation_phase='normal-opposition'
        self.long_allocation_history=deque(maxlen=16)

    def open_wrong(self,accepted=None):
        self.check(False,self.wrong_window,'one complete wrong-short acceptance window')
        self.check(None,self.selected_wrong,'one named original owns short error and long allocation')
        self.check(True,self.protected is not None and self.bridge is not None and self.reward is not None,
            'named wrong window follows the complete original reward and declared bridge')
        short=resident(self.pipeline.model.sources,self.protected)
        self.check(0,short.counter,'named wrong window starts before its original NT0 error update')
        self.wrong_precondition=dict(protected=self.protected,resident=short,
            history=self.bridge['history']%512,enabled=self.pipeline.model.control_pipe[-1])
        self.wrong_acceptance=accepted
        self.wrong_window=True

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
        self.wrong_first=cycle.tokens[0] if cycle.fires[1] and not cycle.flushes[0] else None
        return super().candidates(row,events,cycle,model,phase,previous)

    def checked(self,tick,*candidates):
        super().checked(tick,*candidates)
        if self.applied is not None:
            origin=next((owner for feedback,owner in self.offers if feedback is self.applied.feedback),None)
            for table,index,before,after,role in self.pipeline.model.sources.short.effects:
                if table==1 and role=='allocate':
                    self.long_allocation_history.append(dict(tick=tick,phase=self.preparation_phase,
                        owner=None if origin is None else origin.sequence,index=index,
                        checkpoint=None if origin is None else origin.history.history%512,
                        entry=resident(self.pipeline.model.sources,(table,index)),
                        feedback=self.applied.feedback))
        if self.confirming_long is not None:
            row=self.confirming_long
            self.check(row['written_tick']+2,tick,'new long allocation crosses next full actual comparison')
            self.check(2,self.actual_useful[1][row['index']],'actual long protection initialized independently')
            self.long_allocations[row['owner']]=dict(row,actual_confirmation_tick=tick)
            self.mark(EXTRA[1],tick); self.mark(EXTRA[2],tick)
        self.pending_long=None
        # candidates saves the pre-advance input; its immutable snapshot is
        # present only AFTER the common autonomous comparison and advancement.
        first=self.wrong_first
        if self.wrong_window and first is not None:
            if self.selected_wrong is not None:
                self.check(False,True,'no younger S1 acceptance after named wrong-short endpoint')
            value=provider(self.pipeline.model.sources,first)
            candidate=dict(tick=tick,owner=first.sequence,history=first.history.history%512,
                provider=None if value is None else asdict(value),
                read=self.pipeline.model.sources.short_snapshot(first).prediction.frame)
            self.wrong_candidates.append(candidate)
            if len(self.first_wrong_candidates)<8:
                self.first_wrong_candidates.append(candidate)
            if value is not None and value.key==self.protected and value.counter<4:
                self.selected_wrong,self.selected_wrong_tick=first,tick
                if self.wrong_acceptance is not None:
                    self.wrong_acceptance.set_result(self.pipeline.current_event)
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

    def wrong_receipt(self,source):
        token=self.pipeline.source_token(source)
        self.check(True,self.wrong_window and self.selected_wrong is not None
            and token is self.pipeline.model.published.get(self.selected_wrong.sequence)
            and token.history is self.selected_wrong.history and source.prediction_tick==self.selected_wrong_tick,
            'wrong S3 keeps the exact bounded S1 source, not another equal-key error')
        super().wrong_receipt(source)
        self.wrong_window=False

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
        self.check(indices(bridge.pc,Context.from_recent(bridge.history.history)),frame.read.indices,
            'long consumer read indices derive from the exact declared bridge history')
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
        endpoint=self.pipeline.model.published[self.path[-1]['owner']]
        bridge=self.pipeline.source_token(self.bridge_source)
        self.check(True,self.last_redirect[1] is endpoint.history,
            'short consumer uses the exact declared new read ancestor, not a hash-selected response')
        self.check(indices(endpoint.pc,Context.from_recent(endpoint.history.history)),frame.read.indices,
            'short and long read indices come from the independently programmed path endpoint')
        # MicroTAGE's index-read ancestor and current S1/tag checkpoint are
        # distinct pipeline objects. The old assertion compared the latter
        # twice; they can numerically alias even while the real READ ancestor
        # differs. Prove the actual consumer's declared ancestry instead.
        self.check(endpoint.history.history% (1<<HISTORIES[0]),bridge.history.history% (1<<HISTORIES[0]),'same recent read path identity')
        self.check(True,endpoint.history.history% (1<<HISTORIES[1])!=bridge.history.history% (1<<HISTORIES[1]),'older read path differs within the actual longer-history width')
        self.check(True,source.prediction_tick>self.long['meta_tick'],'short request follows actual long consumption')
        self.short=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),history=token.history.history,read_indices=frame.read.indices,
            read_ancestor_owner=endpoint.sequence,read_history=endpoint.history.history,
            previous_read_ancestor_owner=bridge.sequence,previous_read_history=bridge.history.history)
        self.short_source=source
        self.mark(EXTRA[6],source.meta_tick); self.mark(EXTRA[7],source.meta_tick)
        self.final_source(source)

    def finish_opposition(self,additional_sources=(),*,completion_tick=None):
        self.check(True,self.bridge is not None and self.long is not None and self.short is not None,'exact read ancestor and both consumers required')
        self.check(False,self.wrong_window,'named wrong S1 window has its complete S3 receipt')
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
