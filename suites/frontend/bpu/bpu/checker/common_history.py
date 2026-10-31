"""Actual history is compared to owned final choices, never sampled S2/S3 inputs."""
from collections import deque
from toffee import CheckContext,ScoreboardMode
from suites.frontend.bpu.bpu.model.common_history import CommonDirectionReference,Value,Block,LOOKUP_WINDOW_CAPACITY
from suites.frontend.bpu.bpu.model.selection import Branch,Kind
from suites.frontend.bpu.bpu.coverage.common_history import RULES


class CommonHistoryChecks:
    rules=RULES

    def __init__(self,pipeline,*,observe_state=True,coverage=None):
        self.pipeline=pipeline;self.model=CommonDirectionReference();self.failure=None;self.initialized=False
        self.last_tick=None;self.plans=deque();self.sources={};self.stable=0;self.checked=0;self.last_recovery=None
        self.observe_state=observe_state
        self.coverage=coverage;self.original=None;self.completed_recovery=None;self.consumer=None

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.pipeline.raise_failure()

    def check(self,expected,actual,point):
        self.raise_failure()
        try:self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
            ScoreboardMode.DIRECT,sequence_id=self.last_tick,request=dict(point=point,reference=self.model.value,
                pending=self.model.pending,stable=self.stable)))
        except Exception as error:self.failure=error;raise

    def register_anchor(self,source):
        token=self.pipeline.source_token(source)
        self.check((),Block.from_token(token).conditionals,'reset anchor has no independently learned conditionals')
        checkpoint=self.model.checkpoint(token.history,Block.from_token(token),value=Value())
        self.sources[token.history.sequence]=checkpoint;self.metadata(source,checkpoint,resolve_valid=False)
        return checkpoint

    def metadata(self,receipt,checkpoint,*,resolve_valid=True):
        token=self.pipeline.source_token(receipt)
        self.check(True,checkpoint.owner is token.history,'CommonHR lookup belongs to this exact public source')
        redirect=receipt.meta.redirect['commonHRMeta'];resolve=receipt.meta.resolve['commonHR']
        self.check(int(resolve_valid),resolve['valid'],'public CommonHR validity is checked before comparing payload')
        self.check((checkpoint.value.ghr,checkpoint.value.bw),(redirect['ghr'],redirect['bw']),'owned public redirect history, no metadata golden seed')
        self.check((int(resolve_valid),checkpoint.value.ghr,checkpoint.value.bw),
            (resolve['valid'],resolve['ghr'],resolve['bw']),'owned public resolve history')
        values={} if token.lookup is None else token.lookup.values();seen=set();hits=[]
        for i in range(10):
            position=values.get(f'{i}.position')
            hit=bool(values.get(f'{i}.valid') and values[f'{i}.kind']==Kind.CONDITIONAL and position not in seen)
            hits.append(int(hit))
            if hit:
                seen.add(position);self.check((position,1),(redirect['position'][i],redirect['attribute'][i]['branchType']),
                    'conditional-only deduplicated original branch identity')
        self.check(tuple(hits),tuple(redirect['hitMask']),'BPU exports only conditional dedup hits, not every Main hit')

    def source(self,receipt):
        token=self.pipeline.source_token(receipt);checkpoint=self.sources.get(token.history.sequence)
        self.check(True,checkpoint is not None,'CommonHR source requires an independently certified lookup history')
        self.metadata(receipt,checkpoint);return checkpoint

    def original_source(self,receipt,*,later_conditional):
        source=self.source(receipt)
        self.check((True,65535,255),(source.value.valid,source.value.ghr,source.value.bw),'independent nonzero original lookup history')
        self.check((1,5) if later_conditional else (1,),source.block.conditionals,'first versus unexecuted later conditional identities')
        self.original=receipt,source
        if self.coverage is not None:
            self.coverage.record('reached',self.rules[0],receipt.meta_tick)
            self.coverage.record('reached',self.rules[1],receipt.meta_tick)

    def recovered(self,tick):
        self.check(True,self.original is not None and self.last_recovery is not None,'real original recovery input precedes restored-state check')
        self.check((tick,self.original[1]),self.last_recovery[:2],'restored prefix belongs to the exact original source')
        self.check(True,self.last_tick>tick+2 and self.model.pending is None,'post-restore observation required before endpoint credit')
        self.check(Value(False,65534,254),self.model.value,'one executed not-taken conditional, not the whole predicted block')
        self.completed_recovery=tick
        if self.coverage is not None:
            self.coverage.record('reached',self.rules[3],self.last_tick)
            if self.observe_state:self.coverage.record('reached',self.rules[4],self.last_tick)

    def consumed(self,receipt,*,later_conditional):
        self.check(True,self.completed_recovery is not None and receipt.prediction_tick>self.completed_recovery,'consumer is a fresh post-recovery prediction')
        source=self.source(receipt)
        self.check(Value(True,65533,252) if later_conditional else Value(True,65534,254),source.value,'only actually subsequent conditional outcomes extend recovered history')
        self.consumer=receipt
        if self.coverage is not None:self.coverage.record('reached',self.rules[4],receipt.meta_tick)

    def finish(self,*,public_only):
        self.check(True,self.original is not None and self.completed_recovery is not None,'original source and actual restoration both required')
        if public_only:self.check(True,self.consumer is not None,'valid public consumer required; invalid state alone is not verification')
        self.metadata(self.original[0],self.original[1])
        self.check(False,bool(self.plans),'all planned public recoveries accepted')
        if self.coverage is not None:
            self.coverage.record('reached',self.rules[5],self.last_tick)
            for rule in self.rules:self.coverage.record('checked',rule,self.last_tick)
            self.coverage.finish()

    def plan(self,receipt,request):
        token=self.pipeline.source_token(receipt);checkpoint=self.sources.get(token.history.sequence)
        self.check(True,checkpoint is not None and checkpoint.owner is token.history,'recovery only from reset/fixed-point certified history')
        self.model.require(checkpoint)
        position=request.cfi_pc-(token.pc//16)*16
        branch=Branch(position,request.pc,Kind(request.branch_type),bool(request.taken))
        self.plans.append((checkpoint,branch,request))

    def capture_state(self,event,row):
        if self.failure is not None:return
        try:
            self.last_tick=event.tick
            if not self.initialized:
                if not row['reset']:return
                self.initialized=True
            if row['reset']:
                self.model.reset();self.plans.clear();self.sources.clear();self.stable=0
                self.original=self.completed_recovery=self.consumer=self.last_recovery=None
                return
            self.check(self.pipeline.last_tick,event.tick,'lossless independent pipeline and common-history sample')
            if self.observe_state:self.check(self.model.value.mapping(),row['state'],
                'semantic completed conditional history; later CFIs are not executed prefix')
            self.checked+=1;cycle=self.pipeline.last_cycle;events=self.pipeline.last_events
            completed=None
            if cycle.metadata is not None:completed=Block.from_token(cycle.metadata),cycle.decisions[2].branch
            redirect=None
            if row['redirect']['valid']:
                self.check(True,bool(self.plans),'public recovery has its certified independent source')
                checkpoint,branch,request=self.plans[0];r=row['redirect']
                self.check((request.cfi_pc,request.pc,request.taken,request.branch_type),
                    (r['pc'],r['target'],r['taken'],r['kind']),'complete accepted semantic recovery event')
                self.check((checkpoint.value.ghr,checkpoint.value.bw),(r['meta']['ghr'],r['meta']['bw']),'actual restore input preserves the original certified history')
                positions=tuple(p for hit,p in zip(r['meta']['hits'],r['meta']['positions'],strict=True) if hit)
                self.check(checkpoint.block.conditionals,tuple(sorted(set(positions))),'original conditional-only recovery identity set')
                self.check(len(positions),len(set(positions)),'recovery metadata cannot duplicate a conditional outcome')
                self.check(True,all(kind==1 for hit,kind in zip(r['meta']['hits'],r['meta']['kinds'],strict=True) if hit),
                    'every qualified redirect hit really denotes a conditional branch')
                expected=checkpoint.value.append(checkpoint.block.outcomes(branch,recovering=True),valid=False)
                self.last_recovery=(event.tick,checkpoint,branch,expected);redirect=checkpoint,branch;self.plans.popleft()
                if self.original is not None and checkpoint is self.original[1] and self.coverage is not None:
                    self.coverage.record('reached',self.rules[2],event.tick)
            before=self.model.value;self.model.advance(completed=completed,redirect=redirect)
            steady=(redirect is None and self.model.pending is None and before==self.model.value and all(cycle.fires)
                and not cycle.middle_repair and not cycle.final_repair and before.valid)
            self.stable=self.stable+1 if steady else 0
            # After a full history window of uninterrupted unchanged outcomes,
            # every eligible delayed lookup has this same value. No pointer or
            # actual history is sampled to choose a golden branch.
            if self.stable>=LOOKUP_WINDOW_CAPACITY and cycle.fires[0]:
                issued=self.pipeline.model.stages[0]
                if issued is not None:
                    self.sources[issued.history.sequence]=self.model.checkpoint(issued.history,Block.from_token(issued))
        except Exception as error:self.failure=error
