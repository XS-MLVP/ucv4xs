"""Specialize the existing original-learning checker for an SC-owned teacher."""
from copy import deepcopy

from bpuverify.bpu.checker.indirect_path_ownership import _ObservedChecks
from bpuverify.bpu.coverage.sc_early_learning import Coverage
from bpuverify.bpu.model.sc_early_learning import Program,RULES,direction_ready
from bpuverify.bpu.model.selection import Kind


class Checks(_ObservedChecks):
    completion_rules = RULES

    def __init__(self,profile,coverage=None):
        super().__init__(profile)
        self.program = Program(profile)
        self.coverage = Coverage(profile) if coverage is None else coverage
        self.sc_control = self.teacher = self.SC_witness = None
        self.learning_inputs,self.accepted_SC_inputs = [],[]
        self.consumer_projection = None
        self.consumer_pending = self.consumer_confirmed = None
        self._accepted_witnesses = []
        self._open_witnesses = self._selected_witness = self._middle_witness = None
        self._repair_witness = self._learning_witness = self._restored_witness = None
        self._consumer_witness = self._SC_witness = self._newer_witness = None

    @property
    def bank(self):
        return self.pipeline.model.sources

    def snapshots(self,token):
        return (*super().snapshots(token), self.bank.statistical_snapshot(token),
            self.bank.statistical_snapshot(token,resolved=True),self.bank.queries.snapshot(token))

    def save(self,source):
        token = super().save(source)
        if self.selected is not None and token.sequence==self.selected.sequence:
            self.teacher = source
        return token

    def plan(self,name,source,outcomes):
        token = self.save(source)
        self.check(False,name in self.plans,'feedback name is unique')
        self.check(False,any(self.pipeline.source_token(s) is token for s,_ in self.plans.values()),
            'each feedback has a distinct original, never a replayed metadata object')
        self.plans[name]=source,tuple(outcomes)

    def accepted_feedback(self,request,tick):
        matches = [(name,outcomes) for name,(source,outcomes) in self.plans.items()
            if self.pipeline.source_token(source) is request.origin]
        self.check(1,len(matches),'actual accepted feedback has exactly one original plan')
        name,outcomes = matches[0]
        self.check(outcomes,tuple(b for b in request.branches if b is not None),'complete real outcomes accepted unchanged')
        self.inputs.append(dict(phase=name,owner=request.origin.sequence,tick=tick))
        self._accepted_witnesses.append((name,request.origin,outcomes,tick))
        if name.startswith('SC-negative-experience-'):
            self.accepted_SC_inputs.append(request.origin.sequence)

    def open(self):
        self.check(True,self.sc_control is not None,'SC authority calibrated with a real original before opening')
        self.check(4,len(self.accepted_SC_inputs),'all four distinct SC learning beats actually accepted')
        self.check(4,len(set(self.accepted_SC_inputs)),'no repeated original metadata counted as separate experience')
        self.mark(RULES[11],self.pipeline.last_tick)
        self._open_witnesses = tuple(self.save(source) for source in
            (self.seed,self.stable,self.target_control,self.sc_control))
        return super().open()

    def candidates(self,row,events,cycle,model,phase,previous):
        super().candidates(row,events,cycle,model,phase,previous)
        if self.candidate is not None and not direction_ready(model.sources,self.candidate,self.program):
            self.candidate = None
        return ()

    def check_consumer(self,token):
        early = token.early.branch
        self.check((4,Kind.INDIRECT,self.program.a,True),
            (early.position,early.kind,early.target,early.taken),'fresh NT experience selects the complete early indirect successor')
        # This is a short-history experience. A newer *long* history can have
        # no TAGE provider/SC authority and choose another S3 prediction. Its
        # whole pipeline is still independently compared, not forced to A.
        value = self.bank.statistical_snapshot(token,resolved=True)
        self.consumer_projection = dict(owner=token.sequence,early_target=early.target,
            final_target=value.late.branch.target,final_kind=int(value.late.branch.kind),SC_used=value.prediction.used)

    def checked(self,tick,*candidates):
        before = (self.selected,self.middle,self.repair,self.pending,self.confirmed,self.new_a,self.new_b)
        super().checked(tick,*candidates)
        if self.consumer_pending is not None:
            expected = self.consumer_pending
            self.check(expected['written_tick']+2,tick,'new consumer guidance has its own exact next complete state')
            self.check(0,self.actual_useful[0][expected['index']],
                'new long-context disagreement independently removes the short prediction protection')
            self.consumer_confirmed = dict(expected,confirmed_tick=tick)
            self._newer_witness = deepcopy(self.consumer_confirmed)
            self.consumer_pending = None
            self.mark(RULES[13],tick)
        if before[0] is None and self.selected is not None:
            self._selected_witness = self.selected,self.selected_tick
            self.mark(RULES[0],tick)
        if before[1] is None and self.middle is not None:
            self._middle_witness = deepcopy(self.middle)
            self.mark(RULES[2],tick)
        if before[2] is None and self.repair is not None:
            token = self.cycle.metadata
            value = self.bank.statistical_snapshot(token,resolved=True)
            fields = dict(self.bank.tage_snapshot(token,resolved=True).wanted)
            slot, = [i for i in range(4) if fields.get(f'{i}.has_provider')]
            self.check((3,0,1),(fields[f'{slot}.counter'],fields[f'{slot}.use_provider'],
                fields[f'{slot}.alternative']),'original weak negative provider gives final authority to taken Main')
            self.check((True,1,0,-19),(value.enabled,value.prediction.used[slot],
                value.prediction.directions[slot],value.prediction.sums[slot]),'SC really changes this original final direction')
            self.check(True,value.original.owner is token.history,'SC read and final teacher have the same original owner')
            self.SC_witness = dict(owner=token.sequence,tick=tick,sum=value.prediction.sums[slot],
                used=value.prediction.used[slot],read_history=value.original.history,
                metadata=self.bank.statistical.feedback_histories[token.history.sequence])
            self._SC_witness = value,deepcopy(self.SC_witness)
            self._repair_witness = token,deepcopy(self.repair),self.restored
            wrong = self.cycle.tokens[0]
            for getter in (self.bank.statistical_snapshot,self.bank.queries.snapshot):
                try:
                    getter(wrong)
                except ValueError:
                    pass
                else:
                    self.check(False,True,'cancelled younger query cannot retain SC/history ownership')
            for rule in (RULES[1],RULES[3],RULES[4]):
                self.mark(rule,tick)
        for index,rule in ((3,RULES[5]),(4,RULES[6]),(5,RULES[7])):
            values = (self.selected,self.middle,self.repair,self.pending,self.confirmed,self.new_a,self.new_b)
            if before[index] is None and values[index] is not None:
                self.mark(rule,tick)
        if before[4] is None and self.confirmed is not None:
            self._learning_witness = deepcopy(self.confirmed)
        if before[5] is None and self.new_a is not None:
            self._restored_witness = self.cycle.metadata,deepcopy(self.new_a)
        if before[6] is None and self.new_b is not None:
            self._consumer_witness = self.cycle.metadata,deepcopy(self.new_b),deepcopy(self.consumer_projection)
            self.mark(RULES[8],tick)
            self.mark(RULES[9],tick)
        if self.applied is not None and self.new_b is not None:
            owner = self.offers.get(id(self.applied.feedback))
            if owner is not None and owner.sequence==self.new_b['owner']:
                for table,index,old,new,role in self.bank.short.effects:
                    if table==0 and index==self.confirmed['index'] and role=='useful-decrease':
                        self.check((1,0),(old,new),'new guidance, not original SC feedback, owns protection loss')
                        self.check(True,owner.sequence!=self.repair['owner'],'do not attribute the consumer effect to the original teacher')
                        self.check((2,True),(self.applied.feedback.position,self.applied.feedback.taken),
                            'new long-context final condition opposes its own earlier NT provider')
                        self.consumer_pending = dict(owner=owner.sequence,index=index,written_tick=tick,
                            old_useful=old,new_useful=new,original_teacher=self.repair['owner'])
                        self.mark(RULES[12],tick)

    def finish(self):
        self.check(False,self.closed,'single SC-guided early-learning closure')
        self.check(True,all(v is not None for v in (self.teacher,self.selected,self.middle,self.repair,
            self.SC_witness,self.confirmed,self.new_a,self.new_b,self.consumer_projection,
            self.seed,self.stable,self.target_control,self.sc_control,self.consumer_confirmed)),
            'real teacher, both repairs, actual learning and natural consumer all required')
        self.check(None,self.pending,'no expected-only unconfirmed short-learning effect')
        self.check(None,self.consumer_pending,'new consumer feedback also needs actual confirmation')
        self.check(True,self.acceptance is not None and self.acceptance.done(),'actual S1 acceptance must still have its receipt')
        teacher = self.save(self.teacher)
        self.check(True,self._repair_witness[0] is teacher,'full receipt owns the actual original teacher')
        self.check(self._selected_witness,(self.selected,self.selected_tick),'selected S1 witness cannot be rebound')
        self.check(True,self.selected is self._selected_witness[0],'original S1 token identity cannot be replaced by an equal copy')
        self.check(True,self.selected.history is teacher.history,'accepted S1 and published teacher share exact history ownership')
        self.check(self._middle_witness,self.middle,'original middle report remains unchanged')
        self.check(self._repair_witness[1],self.repair,'original repair report remains unchanged')
        self.check(True,self._repair_witness[2] is self.restored,'exact restored S0 original remains unchanged')
        self.check(self._learning_witness,self.confirmed,'actual learning confirmation remains unchanged')
        self.check(self._restored_witness[1],self.new_a,'restored publication report remains unchanged')
        self.check(self._consumer_witness[1],self.new_b,'natural consumer identity/provider report remains unchanged')
        self.check(self._consumer_witness[2],self.consumer_projection,'new consumer full-target report remains unchanged')
        self.check(self._SC_witness[1],self.SC_witness,'SC selection and original history report remain unchanged')
        self.check(True,self.bank.statistical_snapshot(teacher,resolved=True) is self._SC_witness[0],
            'same immutable SC original, never a later equal payload')
        self.check(self._newer_witness,self.consumer_confirmed,'newer independent protection effect remains unchanged')
        self.check(tuple(self.save(source) for source in (self.seed,self.stable,self.target_control,self.sc_control)),
            self._open_witnesses,'preparation sources cannot be replaced at closure')
        for token in (self._restored_witness[0],self._consumer_witness[0]):
            self.check(True,any(owner is token for _,owner,_,_ in self.saved.values()),'complete new publication receipts required')
        self.check(True,self.repair['owner']<self.new_a['owner']<self.new_b['owner'],'original recovery precedes new natural consumer')
        self.check(set(self.plans),{item['phase'] for item in self.inputs},'every declared real feedback accepted')
        self.check([dict(phase=name,owner=owner.sequence,tick=tick) for name,owner,_,tick in self._accepted_witnesses],
            self.inputs,'actual input acceptance reports cannot be rewritten')
        for source,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(source) is token,'saved public receipt owns the exact published original')
            self.check(True,self.pipeline.model.published.get(token.sequence) is token,'saved original remains owned until explicit release')
            self.check(snapshots,self.snapshots(token),'all nine original domains remain immutable')
            self.check(metadata,source.meta,'complete public metadata remain immutable')
        self.mark(RULES[10],self.pipeline.last_tick)
        self.check(set(RULES),self.reached_rules,'every actual lifetime obligation has its witness')
        for rule,tick in self.coverage.reached.items():
            self.coverage.record('checked',rule,tick)
        self.coverage.finish()
        self.closed = True
        self.facts = dict(profile=self.program.profile,inputs=self.inputs,middle=self.middle,repair=self.repair,
            SC_teacher=self.SC_witness,confirmed=self.confirmed,new_a=self.new_a,new_b=self.new_b,
            consumer=self.consumer_projection,original_domains=9,saved_originals=len(self.saved),
            consumer_own_confirmation=self.consumer_confirmed,
            original_snapshots_immutable=True,genuine_early_conditional=True,natural_consumer=True,
            FastTrain_is_S3_prediction_not_backend_truth=True,complete_FTQ=False)
        return self.facts

    def failure_evidence(self):
        return dict(tick=self.pipeline.last_tick,accepted_feedbacks=self.inputs,selected=self.selected_tick,
            redirect_count=self.redirect_count,last_redirect=self.last_redirect,
            repair=self.repair,confirmed=self.confirmed,new_a=self.new_a,new_b=self.new_b,
            consumer_pending=self.consumer_pending,consumer_confirmed=self.consumer_confirmed,
            SC_teacher=self.SC_witness,short_state=self.bank.short.state())
