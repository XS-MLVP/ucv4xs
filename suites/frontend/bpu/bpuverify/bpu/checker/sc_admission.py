"""Actual valid/ready ownership and learning, not coroutine completion alone."""
from copy import deepcopy

from bpuverify.bpu.checker.statistical_prefix import Checks as PrefixChecks
from bpuverify.bpu.model.sc_admission import Program,BurstProgram
from bpuverify.sc.model.semantic import feedback_needs_read,Context,coordinates,FAMILIES


class Checks(PrefixChecks):
    def __init__(self,profile,coverage,*,program_type=Program):
        super().__init__('conditional-entry.condition-taken',coverage)
        self.program = program_type(profile)
        self.setup = set()
        self.stream = False
        self.steady = 0
        self.proposal = self.source = self.before = self.payload = None
        self.blocked_ticks,self.accepted_ticks,self.overlap_ticks = [],[],[]
        self.patch_offers = []
        self.actual_requests = []
        self.read_receipts = []

    def mark(self,rule):
        # Shared preparation has its own old prefix requirements. They are
        # not this program's hardware coverage or an alternative completion.
        self.setup.add(rule)

    def prove(self,rule,tick=None):
        self.coverage.record(rule,self.pipeline.last_tick if tick is None else tick)

    def candidates(self,row,*args):
        super().candidates(row,*args)
        self.training = row['inputs']['training']
        self.expected_patches = self.bank.sc.preview_learning()[0]
        return ()

    def begin(self,source,resolution):
        self.source,self.proposal = self.save(source),resolution
        self.check(True,resolution.origin is self.source,'one exact published original owns the proposal')
        transaction = self.bank.sc_feedback(resolution,True)
        self.check(self.program.needs_read,feedback_needs_read(transaction),'original qualification decides read need')
        self.before = deepcopy(self.bank.sc.memory),self.bank.sc.thresholds.values
        self.prove('real-used-original')

    def compare_reads(self,tick):
        request = self.events.feedback
        feedback = None if request is None else self.bank.sc_feedback(request,True)
        needed = feedback is not None and feedback_needs_read(feedback)
        context = Context() if feedback is None else Context.from_history(feedback.history)
        bank,indices = coordinates(0 if feedback is None else feedback.pc,context)
        actual = self.observed['statistical']['accepted_reads']
        for table,(family,port) in enumerate(zip(FAMILIES,actual,strict=True)):
            active = needed and (context.common_valid or family not in ('global','backward'))
            self.check(active,bool(port['valid']),'actual accepted SC read belongs to the original qualification and history family')
            if active:
                self.check((indices[table],1<<bank),(port['index'],port['bank']),
                    'actual SC training-read identity is independently derived from the original history')
        if needed:
            self.read_receipts.append(dict(tick=tick,owner=request.origin.sequence,ports=deepcopy(actual)))

    def checked(self,tick,*args):
        super().checked(tick,*args)
        c,p = self.cycle,self.program
        stable = (self.stream and all(t is not None and t.pc==p.loop for t in c.tokens)
            and all(c.fires) and not any(c.flushes) and not c.middle_repair and not c.final_repair
            and all(choice.branch.target==p.loop for choice in c.decisions))
        self.steady = self.steady+1 if stable else 0
        if self.proposal is None:
            return
        self.compare_reads(tick)
        if self.training['valid']:
            payload = {key:deepcopy(value) for key,value in self.training.items() if key not in ('valid','ready')}
            if self.payload is None:
                self.payload = payload
            self.check(self.payload,payload,'full held proposal and all original metadata stay unchanged')
            self.prove('complete-proposal-owned',tick)
            if c.fires[0]:
                self.check(p.loop,c.next_pc,'concurrent request belongs to the independently prepared stream')
                self.overlap_ticks.append(tick)
                self.prove('active-prediction-stream',tick)
            ready = bool(self.observed['statistical']['ready'])
            if not ready:
                self.check(True,p.blocked,'only a declared qualified conflict can hold this proposal')
                self.check(False,bool(self.training['ready']),'SC refusal blocks the whole input')
                self.check([],self.accepted_ticks,'no learning acceptance before conflict release')
                self.check(self.before,(self.bank.sc.memory,self.bank.sc.thresholds.values),
                    'prediction reads cannot perform the held feedback learning')
                self.blocked_ticks.append(tick)
            if self.events.feedback is not None:
                request = self.events.feedback
                self.check(True,request.origin is self.source,'actual input owns the declared old source')
                self.check(self.proposal.branches,tuple(b for b in request.branches if b is not None),
                    'complete executed prefix unchanged at acceptance')
                self.accepted_ticks.append(tick)
                self.actual_requests.append(request)
                self.check(1,len(self.accepted_ticks),'one proposal accepted exactly once')
                if p.blocked:
                    self.check(True,len(self.blocked_ticks)>=2,'at least two real denied opportunities precede release')
                    self.check(False,bool(c.fires[0]),'release removes actual conflicting prediction access')
                else:
                    self.check(True,bool(c.fires[0]),'nonconflicting feedback is accepted during actual prediction')
                self.prove('eligibility-selects-admission',tick)
                self.prove('one-actual-acceptance',tick)
        if self.expected_patches:
            self.check(True,bool(self.accepted_ticks),'an actual owner must precede learning offers')
            self.patch_offers.append((tick,self.expected_patches))

    def finish(self,fresh):
        self.check(1,len(self.accepted_ticks),'one completed actual feedback required')
        self.check(True,bool(self.overlap_ticks),'actual S0 prediction overlapped the submitted feedback')
        self.check(self.program.blocked,bool(self.blocked_ticks),'declared conflict/no-conflict actually happened')
        self.check(1 if self.program.needs_write else 0,len(self.patch_offers),'learning and read-only feedback have different write obligations')
        self.check(int(self.program.needs_read),len(self.read_receipts),'actual training read or no-read suppression')
        token = self.save(fresh)
        old = self.bank.statistical_snapshot(self.source,resolved=True).prediction.read
        new = self.bank.statistical_snapshot(token,resolved=True).prediction.read
        self.check(old.indices,new.indices,'fresh consumer reads the original logical feature identities')
        self.check(self.program.needs_write,old.weights!=new.weights,'fresh consumer sees actual learned or preserved weights')
        if not self.program.needs_write:
            self.check(self.before,(self.bank.sc.memory,self.bank.sc.thresholds.values),'correct SC feedback preserves all weights and thresholds')
        self.prove('actual-learning-effects')
        self.prove('fresh-owned-consumer')
        for receipt,owner,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(receipt) is owner,'exact public owner retained')
            self.check(snapshots,self.snapshots(owner),'all nine original domains remain immutable')
            self.check(metadata,receipt.meta,'public original metadata remains immutable')
        self.prove('original-evidence-preserved')
        result = super().finish(fresh)
        result.update(blocked_ticks=self.blocked_ticks,accepted_ticks=self.accepted_ticks,
            concurrent_prediction_ticks=self.overlap_ticks,SC_needs_read=self.program.needs_read,
            actual_patch_offers=self.patch_offers,thresholds_before=self.before[1],
            actual_training_reads=self.read_receipts,SC_needs_write=self.program.needs_write,
            thresholds_after=self.bank.sc.thresholds.values,fresh_weights_changed=old.weights!=new.weights,
            original_owner=self.source.sequence,fresh_owner=token.sequence,
            original_feedback_is_backend_truth=True,no_bank_sweep=True)
        return result


class BurstChecks(Checks):
    def __init__(self,profile,coverage,*,program_type=BurstProgram):
        super().__init__(profile,coverage,program_type=program_type)
        self.queue = None
        self.payloads = {}
        self.accepted_cycles = []

    def begin_many(self,sources,resolutions):
        p = self.program
        tokens = tuple(self.save(source) for source in sources)
        self.check(p.source_pcs,tuple(token.pc for token in tokens),'declared alternating instruction identities')
        self.check(3,len({token.sequence for token in tokens}),'three distinct real originals, not repeated metadata submission')
        self.queue = tuple(zip(tokens,resolutions,strict=True))
        for token,resolution in self.queue:
            self.check(True,resolution.origin is token,'each queued prefix keeps its exact original')
        self.check((1,0,1),tuple(int(any(self.bank.statistical_snapshot(token,resolved=True).prediction.used))
            for token in tokens),'wrong used head and tail surround a different low-confidence original')
        self.check((True,)*3,tuple(feedback_needs_read(self.bank.sc_feedback(resolution,True))
            for _,resolution in self.queue),'read qualification is independently derived for every original')
        self.before = deepcopy(self.bank.sc.memory),self.bank.sc.thresholds.values
        self.prove('distinct-complete-originals')
        self.prove('eligibility-belongs-to-original')

    def checked(self,tick,*args):
        PrefixChecks.checked(self,tick,*args)
        c,p = self.cycle,self.program
        stable = (self.stream and all(token is not None and token.pc==p.loop for token in c.tokens)
            and all(c.fires) and not any(c.flushes) and not c.middle_repair and not c.final_repair
            and all(choice.branch.target==p.loop for choice in c.decisions))
        self.steady = self.steady+1 if stable else 0
        if self.queue is None:
            return
        self.compare_reads(tick)
        if self.training['valid']:
            index = len(self.accepted_ticks)
            self.check(True,index<len(self.queue),'no fourth or duplicate feedback')
            payload = {key:deepcopy(value) for key,value in self.training.items() if key not in ('valid','ready')}
            self.payloads.setdefault(index,payload)
            self.check(self.payloads[index],payload,'each held queue head keeps its complete input payload')
            self.prove('held-head-preserves-payload',tick)
            if c.fires[0]:
                self.check(p.loop,c.next_pc,'actual prediction stream owns its own request')
                self.overlap_ticks.append(tick)
                self.prove('actual-prediction-overlap',tick)
            if not self.observed['statistical']['ready']:
                self.check(True,p.blocked,'only the declared resource conflict can refuse a feedback')
                self.check(0,index,'blocked queue head cannot be bypassed by a younger feedback')
                self.check(self.before,(self.bank.sc.memory,self.bank.sc.thresholds.values),
                    'no queued feedback learns before actual acceptance')
                self.blocked_ticks.append(tick)
            if self.events.feedback is not None:
                token,resolution = self.queue[index]
                actual = self.events.feedback
                self.check(True,actual.origin is token,'acceptance keeps the ordered exact original')
                self.check(resolution.branches,tuple(b for b in actual.branches if b is not None),
                    'each complete execution prefix is accepted without replacement')
                if p.blocked:
                    self.check(True,len(self.blocked_ticks)>=2,'real repeated conflict precedes every released burst')
                self.check(not p.blocked,bool(c.fires[0]),'actual acceptance after release or during independent reads')
                self.accepted_ticks.append(tick)
                self.accepted_cycles.append(self.cycles)
                self.actual_requests.append(actual)
        if self.expected_patches:
            index = len(self.patch_offers)
            self.check(True,index<len(self.accepted_ticks),'each signed learning beat has an actually accepted original')
            self.patch_offers.append((tick,self.expected_patches))

    def finish_many(self,fresh):
        self.check(3,len(self.accepted_ticks),'all three originals accepted exactly once')
        self.check((1,1),tuple(b-a for a,b in zip(self.accepted_cycles,self.accepted_cycles[1:])),
            'queued originals accepted on adjacent cycles, not serialized by commit waits')
        self.check(self.program.blocked,bool(self.blocked_ticks),'actual declared resource relation')
        self.check(True,bool(self.overlap_ticks),'feedback submission overlaps actual prediction')
        self.check(3,len(self.patch_offers),'three independently compared complete signed learning beats')
        self.check(3,len(self.read_receipts),'three actual SC reads keep their own accepted originals')
        self.prove('actual-ordered-adjacent-acceptances')
        self.prove('all-signed-learning-effects')
        self.check((self.program.b,self.program.x),tuple(source.prediction.start_pc for source in fresh),
            'both instruction identities have fresh consumers')
        for original,receipt in zip(self.queue[:2],fresh,strict=True):
            token,_ = original
            old = self.bank.statistical_snapshot(token,resolved=True).prediction.read
            new = self.bank.statistical_snapshot(self.save(receipt),resolved=True).prediction.read
            self.check(old.indices,new.indices,'fresh consumer retains its own logical features')
            self.check(True,old.weights!=new.weights,'both branches consume the independently predicted learning effects')
        self.prove('fresh-consumers-for-both-branches')
        for receipt,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(receipt) is token,'queued and fresh original identity preserved')
            self.check(snapshots,self.snapshots(token),'old reads are not recomputed from new weights')
            self.check(metadata,receipt.meta,'complete public original metadata remains immutable')
        self.prove('immutable-old-evidence')
        result = PrefixChecks.finish(self,fresh[0])
        result.update(queued_originals=[dict(owner=token.sequence,pc=token.pc) for token,_ in self.queue],
            accepted_ticks=self.accepted_ticks,accepted_cycles=self.accepted_cycles,blocked_ticks=self.blocked_ticks,
            concurrent_prediction_ticks=self.overlap_ticks,actual_patch_offers=self.patch_offers,
            actual_training_reads=self.read_receipts,
            thresholds_before=self.before[1],thresholds_after=self.bank.sc.thresholds.values,
            fresh_consumers=[self.save(source).sequence for source in fresh],
            used_qualification=(1,0,1),distinct_PHR_contexts_proven=False,no_bank_sweep=True)
        return result


class ContextBurstChecks(BurstChecks):
    """The old queue engine with independently distinct original histories."""
    def __init__(self,profile,coverage):
        from bpuverify.bpu.model.sc_admission import ContextBurstLayout
        super().__init__(profile,coverage,program_type=ContextBurstLayout)
        self.contexts={}
        self.original_controls={}
        self.current_controls={}
        self.learning_owners=[]
        self.old_numeric=[]
        self.completed_queue=None

    def close_submissions(self):
        self.check(len(self.program.truths),len(self.accepted_ticks),'all original submissions complete before changing program')
        self.check(8,len(self.learning_owners),'all original learning completed before the return program')
        self.completed_queue,self.queue=self.queue,None

    def context_source(self, receipt, context):
        token=self.save(receipt)
        original=self.bank.statistical_snapshot(token,resolved=True)
        history=self.bank.queries.snapshot(token)
        self.check((True,*self.program.history(context),0),
            (history.read.valid,history.read.ghr,history.read.bw,history.loop),
            'different executed incoming paths retain their own valid nonzero history')
        self.check(history.read,history.metadata,'uninterrupted source read and published history agree')
        self.check(self.bank.queries.sc_history(token),original.original.history,'SC belongs to the original query history')
        self.contexts[token.sequence]=context
        slot,=[i for i,b in enumerate(original.branches) if b is not None and b.position==self.program.position]
        return token,original,slot

    def provider(self, receipt, context):
        token,original,slot=self.context_source(receipt,context)
        fields=dict(self.bank.tage_snapshot(token,resolved=True).wanted)
        self.check((True,self.program.provider_counter),
            (bool(fields[f'{slot}.has_provider']),fields[f'{slot}.counter']),
            'each original context has its real declared TAGE experience')
        return token,original,slot

    def begin_many(self, sources, resolutions):
        p=self.program
        tokens=tuple(self.save(source) for source in sources)
        self.check(len(p.truths),len({t.sequence for t in tokens}),'all ten originals have distinct real ages')
        self.check(p.source_pcs,tuple(t.pc for t in tokens),'one branch is distinguished by its real incoming contexts')
        self.queue=tuple(zip(tokens,resolutions,strict=True))
        for token,resolution in self.queue:
            self.check(True,resolution.origin is token,'each feedback retains the exact published original')
        expected_contexts=tuple(p.capture_contexts[i] for i in p.arrival_order)
        self.check(expected_contexts,tuple(self.contexts[t.sequence] for t in tokens),'arrival order differs from age only as declared')
        ages=tuple(t.sequence for t in tokens)
        self.check(ages,tuple(sorted(ages,reverse=p.profile.startswith('young-first.'))),'real old-first or young-first feedback order')
        needs=tuple(feedback_needs_read(self.bank.sc_feedback(r,True)) for _,r in self.queue)
        self.check(tuple(not truth or not p.agrees for truth in p.truths),needs,'read need belongs to each old original')
        self.before=deepcopy(self.bank.sc.memory),self.bank.sc.thresholds.values
        self.old_numeric=[self.numeric_consumer(source) for source in sources]
        a,b=(self.original_controls[context].original.read for context in p.contexts)
        for family in (2,3,4,5):
            self.check(True,a.indices[family]!=b.indices[family],'global and backward experience have genuinely private identities')
        for family in (6,7):
            self.check(a.indices[family],b.indices[family],'loop and bias experience is genuinely shared')
        self.prove('distinct-complete-originals')
        self.prove('eligibility-belongs-to-original')
        self.prove('distinct-valid-nonzero-contexts')
        self.prove('original-age-vs-arrival-order')

    def candidates(self,row,*args):
        self.learning_original=None if self.bank.sc.learning is None else self.bank.sc.learning[0]
        return super().candidates(row,*args)

    def checked(self,tick,*args):
        previous=len(self.patch_offers)
        super().checked(tick,*args)
        if self.queue is not None and self.training['valid'] and self.cycle.fires[0]:
            lookup=self.observed['statistical']['lookup']
            self.check((True,0,0),(bool(lookup['valid']),lookup['ghr'],lookup['bw']),
                'the current valid-zero prediction stream cannot replace either old nonzero context')
        if self.queue is not None and len(self.patch_offers)>previous:
            indices=[i for i,taken in enumerate(self.program.truths) if not taken]
            self.check(True,previous<len(indices),'correct old originals cannot become extra learning beats')
            owner,resolution=self.queue[indices[previous]]
            self.check(self.bank.sc_feedback(resolution,True),self.learning_original,
                'complete learning beat has the next accepted qualifying original, not a current-history substitute')
            self.check(tuple(range(8)),tuple(patch[0] for patch in self.expected_patches),'every qualified beat learns all five feature families')
            self.learning_owners.append(owner.sequence)

    def finish_context_burst(self, fresh):
        p=self.program
        queue=self.completed_queue
        self.check(True,queue is not None,'the original feedback cohort has an explicit completion boundary')
        self.check(len(p.truths),len(self.accepted_ticks),'each queued original accepted once')
        self.check((1,)*(len(p.truths)-1),tuple(b-a for a,b in zip(self.accepted_cycles,self.accepted_cycles[1:])),
            'actual feedbacks accept on adjacent cycles without waiting for previous writeback')
        self.check(p.blocked,bool(self.blocked_ticks),'the declared head conflict really occurs')
        self.check(True,bool(self.overlap_ticks),'queued feedback overlaps actual prediction')
        wanted_owners=tuple(t.sequence for (t,_),truth in zip(queue,p.truths,strict=True) if not truth)
        self.check(wanted_owners,tuple(self.learning_owners),'all eight wrong originals learn and neither correct original relearns')
        expected_reads=tuple(t.sequence for t,r in queue if feedback_needs_read(self.bank.sc_feedback(r,True)))
        self.check(expected_reads,tuple(row['owner'] for row in self.read_receipts),'actual training reads retain each old qualification and context')
        self.prove('actual-ordered-adjacent-acceptances')
        self.prove('all-signed-learning-effects')
        consumers=[]
        for context,receipt in zip(p.contexts,fresh,strict=True):
            token,value,_=self.provider(receipt,context)
            before=self.original_controls[context]
            self.check(before.original.read.indices,value.original.read.indices,'fresh consumer returns to its own logical features')
            current=self.current_controls[context].original.read
            self.check(current.indices,value.original.read.indices,'before/after burst consumers use the same features')
            self.check(True,all(old!=new for old,new in zip(current.weights,value.original.read.weights,strict=True)),
                'all five changed families come from this feedback burst, not the confidence preparation')
            self.check(True,all(old!=new for old,new in zip(before.original.read.weights,value.original.read.weights,strict=True)),
                'each context consumes all five changed families, including shared and private experience')
            consumers.append(dict(context=context,owner=token.sequence,numeric=self.numeric_consumer(receipt),
                weights_before_burst=current.weights,weights=value.original.read.weights))
        self.prove('fresh-consumers-for-both-contexts')
        self.prove('shared-and-private-feature-effects')
        self.prove('all-context-numeric-consumers')
        for receipt,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(receipt) is token,'all source identities remain owned')
            self.check(snapshots,self.snapshots(token),'all nine old evidence domains remain immutable')
            self.check(metadata,receipt.meta,'later learning cannot rewrite old public metadata')
        self.prove('immutable-old-evidence')
        result=dict(profile=p.profile,queued_originals=[dict(owner=t.sequence,context=self.contexts[t.sequence]) for t,_ in queue],
            accepted_ticks=self.accepted_ticks,accepted_cycles=self.accepted_cycles,read_receipts=self.read_receipts,
            learning_owners=self.learning_owners,actual_patch_offers=self.patch_offers,consumers=consumers,
            original_numeric_reads=self.old_numeric,
            blocked_ticks=self.blocked_ticks,concurrent_prediction_ticks=self.overlap_ticks,
            original_contexts_valid_and_nonzero=True,actual_learning_reads_current_committed_weights=True,
            adjacent_feedbacks_are_not_assumed_to_forward_uncommitted_weight_updates=True,
            complete_FTQ=False,no_bank_sweep=True)
        self.coverage.finish()
        return result
