"""Cross-block original ownership, actual learning and fresh consumer closure."""
from copy import deepcopy
from dataclasses import asdict
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.model.cross_block_learning import program,RULES
from suites.frontend.bpu.bpu.model.ahead_sources import old_history
from suites.frontend.bpu.bpu.model.early_direction_sources import context
from suites.frontend.bpu.bpu.model.early_opposition import provider,resident
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.utage.model.semantic import indices,tag,Entry


class Checks(EarlyDirectionChecks):
    completion_rules=RULES
    def __init__(self,coverage,profile):
        self.program=program(profile); super().__init__(coverage,self.program.b)
        self.saved={}; self.plans={}; self.inputs=[]; self.early={}; self.frames={}
        self.read_origin=None; self.offers={}; self.pending=None; self.confirmed={}; self.final=None; self.auxiliary_allocations=[]; self.repairs={}

    def save(self,source):
        token=self.pipeline.source_token(source)
        self.check(True,self.pipeline.model.published.get(token.sequence) is token,'exact published original, not copied token')
        self.saved.setdefault(source.meta_tick,(source,token,self.pipeline.model.sources.short_snapshot(token),deepcopy(getattr(source,'meta',None))))
        return token

    def plan_resolution(self,phase,source):
        token=self.save(source); expected=self.program.resolution(phase)
        self.check(expected[0],token.pc,'declared source block owns its real instruction')
        self.check(False,phase in self.plans,'one declared original per discovery or outcome')
        if phase in ('predecessor','conditional'):
            self.check(False,any(e.hit for row in source_entries(token.lookup) for e in row),'genuine cold Main discovery')
        if phase=='not-taken':
            self.check(True,self.early.get(self.program.b)==source.meta_tick,'not-taken resolves the named early B original')
        if phase=='fallback':
            self.check(True,'not-taken' in {r['phase'] for r in self.inputs},'conditional outcome precedes later discovery')
            self.check(False,any(e.hit and e.position==4 for row in source_entries(token.lookup) for e in row),'later B branch genuinely absent')
            self.check(True,source.prediction_tick>self.inputs[-1]['tick'],'later discovery uses a fresh request')
        self.plans[phase]=source

    def early_consumer(self,source):
        token=self.save(source); p=self.program
        self.check(True,token.pc in (p.a,p.b),'one of the two real program blocks')
        position,kind,target=(4,2,p.b) if token.pc==p.a else (2,1,p.a)
        branch=token.early.branch
        self.check(('ahead',position,kind,True,target),
            (token.early.source,branch.position,int(branch.kind),branch.taken,branch.target),'actual early edge, not Main-only correctness')
        self.early[token.pc]=source.meta_tick
        if len(self.early)==2: self.mark(RULES[1],source.meta_tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        self.events,self.cycle=events,cycle
        self.previous_frame=model.sources.short.frame; self.previous_older=model.sources.short.older
        self.applied=model.sources.short.learning
        self.actual_useful=row['observed']['early_direction']['useful']
        return ()

    def reached(self,tick,*candidates): pass

    def frame_origin(self,frame):
        value=self.frames.get(id(frame))
        self.check(True,value is not None and value[0] is frame,'frame keeps the exact read ancestor')
        origin=value[1]
        if origin is not None:
            # Pipeline stages create new immutable Token envelopes; the
            # original Checkpoint identity must remain exactly the same.
            for field in ('token','history_token'):
                pending=origin[field]
                if not origin['awaiting_'+field]: continue
                published=self.pipeline.model.published.get(pending.sequence)
                self.check(True,published is not None and published.history is pending.history,
                    'read and old-history checkpoints survive actual stage progression and publication')
                origin[field]=published; origin['awaiting_'+field]=False
        return origin

    def verify_cross_block(self,token,frame):
        origin=self.frame_origin(frame)
        self.check(True,origin is not None,'a real read ancestor exists')
        owner=origin['token']; self.check(True,owner is not None,'read ancestor owns a real pipeline token')
        self.check(True,self.pipeline.model.published.get(owner.sequence) is owner,'read ancestor was actually published')
        history_owner=origin['history_token']
        self.check(True,history_owner is not None and self.pipeline.model.published.get(history_owner.sequence) is history_owner,
            'older history has its own exact published owner')
        self.check((self.program.a,self.program.b,4,2,True),
            (owner.pc,owner.middle.branch.target,owner.middle.branch.position,int(owner.middle.branch.kind),owner.middle.branch.taken),
            'actual exact A-to-B direct edge owns the ahead read')
        if owner.middle_corrected:
            self.check(True,owner.sequence in self.repairs,'different early A target has its own actual S2 correction')
        else:
            self.check(owner.middle.branch,owner.early.branch,'without actual correction A already predicts the exact edge')
        self.check((self.program.b,self.program.b),(token.pc,frame.pc),'B owns matching and feedback identity')
        self.check(context(history_owner.history),origin['context'],'read hash uses the older B checkpoint, not the issued A checkpoint')
        self.check(context(owner.history),frame.context,'B tag matching uses the issued A checkpoint')
        self.check(indices(origin['pc'],origin['context']),frame.read.indices,'indices belong to original A path, not current B')
        self.check(True,frame.read.indices!=indices(frame.pc,frame.context),'cross-block relation is genuinely distinct')
        return dict(owner=owner.sequence,pc=origin['pc'],history=owner.history.history,
            old_history_owner=history_owner.sequence,old_history_pc=history_owner.pc,old_history=history_owner.history.history,indices=frame.read.indices,
            early=asdict(owner.early.branch),exact=asdict(owner.middle.branch),
            middle_corrected=owner.middle_corrected,correction_tick=self.repairs.get(owner.sequence),
            matching_pc=frame.pc,matching_history=frame.context.folds,coherent_B_indices=indices(frame.pc,frame.context))

    def checked(self,tick,*candidates):
        model=self.pipeline.model; sources=model.sources; short=sources.short; events=self.events; cycle=self.cycle
        if cycle.middle_repair: self.repairs[cycle.tokens[1].sequence]=tick
        if self.pending is not None:
            record=self.pending
            self.check(record['written_tick']+2,tick,'next full actual comparison, never predicted state alone')
            self.check(1,self.actual_useful[0][record['index']],'actual cross-block allocation protection initialized')
            record=dict(record,actual_confirmation_tick=tick)
            self.confirmed[record['index'],record['tag']]=record; self.pending=None
            self.mark(RULES[7],tick)
        last=sources.last_short_events; frame=short.frame
        if last.select and last.enabled and last.ready:
            parent=self.previous_older if last.override=='s3' else self.previous_frame if last.override=='s2' else None
            origin=self.frames.get(id(parent),(None,None))[1] if last.override is not None else self.read_origin
            if frame is not None: self.frames[id(frame)]=(frame,origin)
            checkpoint=old_history(events,cycle,model.stages[0] if cycle.fires[0] else None)
            history_token=next((t for t in (*cycle.tokens,model.stages[0]) if t is not None and t.history is checkpoint),None)
            if history_token is None and checkpoint is not None:
                history_token=next((t for t in model.published.values() if t.history is checkpoint),None)
            token=model.stages[0] if cycle.fires[0] else None
            self.read_origin=dict(token=token,history_token=history_token,
                awaiting_token=token is not None and token.middle is None,
                awaiting_history_token=history_token is not None and history_token.middle is None,
                pc=last.read_pc,context=last.read_context,tick=tick)
        if events.feedback is not None:
            request=events.feedback; token=request.origin
            phase=next((name for name,source in self.plans.items() if self.pipeline.source_token(source) is token),None)
            self.check(True,phase is not None,'only a named exact original may feed the program')
            branch,=tuple(b for b in request.branches if b is not None)
            self.check(self.program.resolution(phase),
                (token.pc,branch.position,branch.target,int(branch.kind),branch.taken),'complete semantic outcome and target')
            self.check((True,0),(branch.mispredict,int(branch.action)),'no invented call or partial discovery')
            active=phase in ('not-taken','fallback') and self.program.flowing
            self.check(active,events.prediction_ready,'declared held/flowing source admission')
            self.check(active,cycle.fires[1],'prediction advances independently of old feedback in flowing mode')
            self.check(True,cycle.tokens[0] is not None and cycle.tokens[0] is not token,'old original is not rebound to current younger S1')
            self.inputs.append(dict(phase=phase,owner=token.sequence,tick=tick,pc=token.pc,
                prediction_ready=events.prediction_ready,S1_advances=cycle.fires[1],S1_flushed=cycle.flushes[0],
                current_S1=cycle.tokens[0].sequence))
            self.accepted_ticks.append(tick)
            if phase=='conditional': self.mark(RULES[0],tick)
            if phase=='not-taken': self.mark(RULES[2],tick)
            if phase=='fallback': self.mark(RULES[3],tick); self.mark(RULES[4],tick)
        if self.applied is not None:
            owner=self.offers.get(id(self.applied.feedback))
            if owner is not None and owner.pc==self.program.b:
                for table,index,before,after,role in short.effects:
                    if table!=0 or role!='allocate': continue
                    feedback=self.applied.feedback; saved=sources.short_snapshot(owner)
                    frame=saved.prediction.frame; raw=self.frames.get(id(frame),(None,None))[1]
                    # Recovery also creates legitimate transient reads. They
                    # remain fully compared, but do not prove the declared
                    # normal A->B relation and get no lifecycle credit here.
                    ancestor=None if raw is None else raw['token']
                    if ancestor is None or raw['pc']!=self.program.a or frame.context!=context(ancestor.history):
                        self.auxiliary_allocations.append(dict(owner=owner.sequence,index=index,role=role,tick=tick))
                        continue
                    origin=self.verify_cross_block(owner,frame)
                    self.check((4,True,2),(feedback.position,feedback.taken,feedback.kind),'later B branch qualifies earlier conditional as NT')
                    intended=tag(feedback.pc,feedback.context,0)
                    self.check(Entry(True,intended,2,3),resident(sources,(0,index)),'new short experience owns B identity and NT confidence')
                    self.pending=dict(owner=owner.sequence,index=index,tag=intended,before=before,after=after,
                        counter=3,written_tick=tick,read_ancestor=origin)
                    self.mark(RULES[5],tick); self.mark(RULES[6],tick)
        if last.feedback is not None and cycle.tokens[2] is not None:
            self.offers[id(last.feedback)]=cycle.tokens[2]

    def negative_consumer(self,source):
        token=self.save(source); value=provider(self.pipeline.model.sources,token)
        self.check(True,value is not None and value.table==0 and value.position==2 and value.counter<4,'new actual short NT consumer')
        frame=self.pipeline.model.sources.short_snapshot(token).prediction.frame
        origin=self.verify_cross_block(token,frame); allocation=self.confirmed.get((value.index,value.tag))
        self.check(True,allocation is not None,'same actual confirmed learned identity')
        self.check(True,source.prediction_tick>allocation['actual_confirmation_tick'],'new consumer request follows actual learning confirmation')
        self.check(True,source.prediction_tick>self.inputs[-1]['tick'],'consumer follows all named outcomes')
        for branch in (token.early.branch,token.middle.branch):
            self.check((4,self.program.a,2,True,0),(branch.position,branch.target,int(branch.kind),branch.taken,int(branch.action)),
                'B conditional NT selects real later B-to-A edge at early and exact levels')
        self.consumer=source
        self.final=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),early=asdict(token.early.branch),exact=asdict(token.middle.branch),
            read_ancestor=origin,allocation=allocation)
        self.mark(RULES[8],source.meta_tick)

    def finish(self):
        self.check(False,self.closed,'one complete lifetime')
        self.check(True,self.consumer is not None and self.final is not None,'new complete public consumer required')
        self.check(None,self.pending,'no expected-only allocation is still awaiting actual confirmation')
        self.check(('predecessor','conditional','not-taken','fallback'),tuple(r['phase'] for r in self.inputs),'complete owned discoveries and outcomes')
        self.check({self.program.a,self.program.b},set(self.early),'both real early targets were consumed')
        token=self.save(self.consumer); sources=self.pipeline.model.sources
        self.check(self.final['provider'],asdict(provider(sources,token)),'consumer report retains its actual original provider')
        frame=sources.short_snapshot(token).prediction.frame
        self.check(self.final['read_ancestor'],self.verify_cross_block(token,frame),'consumer retains all three exact ancestors')
        self.check(self.final['allocation'],self.confirmed.get((self.final['provider']['index'],self.final['provider']['tag'])),
            'consumer keeps the actual confirmed allocation')
        for record in self.confirmed.values():
            original=self.pipeline.model.published.get(record['owner'])
            self.check(True,original is not None,'claimed learning original remains published')
            original_frame=sources.short_snapshot(original).prediction.frame
            self.check(record['read_ancestor'],self.verify_cross_block(original,original_frame),'allocation retains its exact read and repair receipts')
            self.check((0,1,3),(record['before'],record['after'],record['counter']),'new identity protection and NT initialization')
            self.check(record['written_tick']+2,record['actual_confirmation_tick'],'allocation retains next actual comparison')
        for source,token,snapshot,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(source) is token,'source receipt cannot be rebound')
            self.check(snapshot,self.pipeline.model.sources.short_snapshot(token),'frozen original short snapshot cannot change')
            self.check(metadata,getattr(source,'meta',None),'full original public metadata cannot change')
        self.mark(RULES[9],self.consumer.meta_tick)
        self.check(set(RULES),self.reached_rules,'all source, actual state and consumer obligations')
        self.check(False,self.pipeline.model.sources.main_pending(),'logical source learning must mature')
        for rule in RULES: self.coverage.record('checked',rule,self.consumer.meta_tick)
        self.coverage.finish(); self.closed=True

    def snapshot(self):
        return dict(profile=self.program.name,closed=self.closed,completed=sorted(self.reached_rules),
            inputs=self.inputs,early_blocks=sorted(self.early),consumer=self.final,
            confirmed_allocations=list(self.confirmed.values()),original_count=len(self.saved),
            auxiliary_allocations_fully_compared=self.auxiliary_allocations,
            full_FTQ_source_eligibility_proved=False,full_PHR_and1024protection_cells_compared=True)
