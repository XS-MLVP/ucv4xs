"""A positive provider must belong to the earlier source-qualified T learning."""
from dataclasses import replace

from bpuverify.bpu.checker.early_opposition import EarlyOppositionChecks
from bpuverify.bpu.coverage.early_positive import RULES,EXTRA_RULES
from bpuverify.bpu.model.early_opposition import provider,ahead_owner,resident,main_counter,is_opposed,steady_history,CONDITIONAL,FALLBACK
from bpuverify.bpu.model.early_positive import PositiveSeed


class EarlyPositiveChecks(EarlyOppositionChecks):
    completion_rules=RULES

    def __init__(self,coverage,pc):
        super().__init__(coverage,pc)
        self.seeds={};self.pending_seeds=[];self.confirming_seeds=()
        self.protected_positive={};self.positive_owners={}
        self.seed=None
        self.pool_declared=False
        self.positive_key=self.positive_entry=self.positive_useful=None
        self.negative_base=self.positive_prepared=self.positive_opposed=None
        self.negative_confirmed=()
        self.return_candidates=[]

    def candidates(self,row,events,cycle,model,phase,previous):
        result=super().candidates(row,events,cycle,model,phase,previous)
        self.confirming_seeds=tuple(self.pending_seeds)
        for seed in self.confirming_seeds:
            self.check(seed.useful,model.sources.short.useful[seed.key[0]].get(seed.key[1],0),
                'seed allocation is at its next complete useful comparison boundary')
        return result

    def checked(self,tick,*candidates):
        # Keep the exact immutable feedback object association, not equality
        # of PC/index payloads belonging to different source tasks.
        owner=None if self.applied is None else next((owner for feedback,owner in self.offers
            if feedback is self.applied.feedback),None)
        super().checked(tick,*candidates)
        if self.direction_taken and self.current_token is not None and self.current_token.pc==self.pc and len(self.return_candidates)<8:
            token=self.current_token;sources=self.pipeline.model.sources
            self.return_candidates.append(dict(tick=tick,sequence=token.sequence,provider=provider(sources,token),
                ahead=ahead_owner(sources,token),choice=token.early))
        for seed in self.confirming_seeds:
            self.check(seed.written+2,tick,'seed effect confirmed one actual boundary later')
            self.seeds[seed.key]=replace(seed,compared=tick)
            self.mark(EXTRA_RULES[0],tick)
        self.pending_seeds=[]
        if self.direction_taken and self.current_token is not None and self.current_token.sequence in self.opposed_owners:
            value=provider(self.pipeline.model.sources,self.current_token)
            self.positive_owners[self.current_token.sequence]=value.key
        if self.strong is None or owner is None or self.pool_declared:return
        feedback=self.applied.feedback
        if (feedback.position,feedback.taken,feedback.kind)!=(CONDITIONAL,True,1):return
        if self.pipeline.model.published.get(owner.sequence) is not owner:return
        sources=self.pipeline.model.sources
        for table,index,before,after,role in sources.short.effects:
            if role!='allocate':continue
            entry=resident(sources,(table,index))
            if not entry.valid or entry.position!=CONDITIONAL or entry.counter!=4:continue
            self.pending_seeds.append(PositiveSeed(owner,sources.short_snapshot(owner),(table,index),entry,after,tick))

    def protect_seed(self):
        self.check(False,self.pool_declared,'declare the positive candidate pool exactly once before driving')
        self.check(True,self.opposed is not None and bool(self.confirmed_increases),'negative-polarity actual proof precedes positive return')
        self.check(True,bool(self.seeds) and all(seed.compared is not None for seed in self.seeds.values()),'positive seeds come from confirmed original-source learning')
        self.check([],self.pending_seeds,'seed actual confirmation is complete')
        self.check(None,self.pending_effect,'negative useful effects have completed actual checking')
        sources=self.pipeline.model.sources
        for key,seed in self.seeds.items():
            entry=resident(sources,key);useful=sources.short.useful[key[0]].get(key[1],0)
            if ((entry.valid,entry.tag,entry.position)!=(True,seed.entry.tag,CONDITIONAL)
                    or entry.counter<4 or useful>=3):continue
            self.check(True,key!=self.protected,'positive and negative providers are distinct semantic keys')
            self.protected_positive[key]=(seed,entry,useful)
        self.check(True,bool(self.protected_positive),'freeze eligible independently learned T identities BEFORE driving the return')
        self.pool_declared=True
        self.negative_confirmed=tuple(self.confirmed_increases)
        self.returning=False

    def negative_base_source(self,source):
        self.check(True,bool(self.protected_positive),'positive keys were independently declared before biasing the base')
        self.check(None,self.negative_base,'one negative-base source')
        self.check(True,source.prediction_tick>self.opposed.meta_tick,'negative base uses a fresh post-proof request')
        token=self.save(source);sources=self.pipeline.model.sources
        self.check(0,main_counter(token),'independent Main remains strongly negative')
        self.check(True,steady_history(token,FALLBACK),'negative alias has the actual fallback history')
        self.check((self.base_owner,0),ahead_owner(sources,token),'same complete Ahead owner is strongly negative')
        frame=sources.short_snapshot(token).prediction.frame
        for key,(seed,entry,useful) in self.protected_positive.items():
            self.check(True,frame is not None and frame.read.indices[key[0]]!=key[1],'negative alias reads a different MicroTAGE context')
            self.check(entry,resident(sources,key),'negative alias preserves every declared positive entry')
            self.check(useful,sources.short.useful[key[0]].get(key[1],0),'negative alias preserves every declared positive useful')
        self.negative_base=source;self.mark(EXTRA_RULES[1],source.meta_tick)

    def main_positive(self,source):
        self.check(True,self.negative_base is not None,'negative base is proven before changing Main')
        self.check(None,self.positive_prepared,'one positive Main-only preparation')
        self.check(True,source.prediction_tick>self.negative_base.meta_tick,'positive preparation has a fresh owner')
        token=self.save(source);sources=self.pipeline.model.sources
        self.check(3,main_counter(token),'ordinary resolves saturate Main positive')
        self.check(True,steady_history(token,CONDITIONAL),'positive Main-only history is ready')
        self.check(False,sources.snapshot(token).enabled,'fast learners are disabled during Main-only preparation')
        self.check(0,sources.ahead.counters[self.base_owner],'negative Ahead base is retained')
        for key,(seed,entry,useful) in self.protected_positive.items():
            self.check(entry,resident(sources,key),'Main-only preparation cannot rewrite a declared positive seed')
            self.check(useful,sources.short.useful[key[0]].get(key[1],0),'Main-only preparation cannot alter declared positive useful')
        self.check((None,None),(sources.short.offered,sources.short.learning),'no old fastTrain crosses the tracking-mode boundary')
        self.check(None,self.pending_effect,'no unconfirmed old useful write is discarded')
        self.positive_prepared=source
        self.direction_taken=True;self.gain_rule=EXTRA_RULES[4];self.returning=True
        self.confirmed_increases=[];self.opposed_owners.clear();self.offers.clear()
        self.mark(EXTRA_RULES[2],source.meta_tick)

    def qualifies_current_source(self,sources,token):
        if not self.direction_taken:return super().qualifies_current_source(sources,token)
        value=provider(sources,token)
        if not is_opposed(sources,token,taken=True) or value.key not in self.protected_positive:return False
        seed,entry,useful=self.protected_positive[value.key]
        return value.tag==seed.entry.tag and value.position==CONDITIONAL

    def tracks_useful_key(self,key):
        return key in self.protected_positive if self.direction_taken else super().tracks_useful_key(key)

    def positive_consumer(self,source):
        self.check(True,self.positive_prepared is not None,'positive opposition follows independent preparation')
        self.check(None,self.positive_opposed,'one named positive opposed consumer')
        self.check(True,source.prediction_tick>self.positive_prepared.meta_tick,'positive consumer follows its own Main-only preparation')
        token=self.save(source);sources=self.pipeline.model.sources;value=provider(sources,token)
        self.check(True,is_opposed(sources,token,taken=True),'valid positive provider disagrees with NT base')
        self.check(True,self.qualifies_current_source(sources,token),'provider belongs to the predeclared independently learned pool')
        self.positive_key=value.key
        self.seed,self.positive_entry,self.positive_useful=self.protected_positive[value.key]
        self.check((self.seed.key,self.seed.entry.tag,CONDITIONAL),(value.key,value.tag,value.position),'consume the previously declared original-source seed')
        self.check((CONDITIONAL,self.pc,True,1,'ahead-direction'),
            (token.early.branch.position,token.early.branch.target,token.early.branch.taken,int(token.early.branch.kind),token.early.source),
            'positive provider selects the earlier conditional, not the later direct fallback')
        self.check((),self.pipeline.corrections_for_source(source),'positive S1 already agrees with independent Main')
        self.check(True,token.sequence in self.opposed_owners,'positive source has passed complete coherent S3 comparison')
        self.check(value.key,self.positive_owners.get(token.sequence),'exact coherent source owns the selected positive key')
        self.positive_opposed=source;self.mark(EXTRA_RULES[3],source.meta_tick)

    def finish_positive(self,additional_sources=(),*,completion_tick=None):
        self.check(True,self.positive_opposed is not None,'fresh positive public consumer is required')
        self.check(True,bool(self.negative_confirmed) and bool(self.confirmed_increases),'both polarities have their own actually confirmed useful increases')
        self.check([],self.pending_seeds,'no incomplete seed obligation')
        token=self.pipeline.source_token(self.positive_opposed)
        self.check(True,any(row[0]==token.sequence for row in self.confirmed_increases),'named positive consumer owns its own actually confirmed increase')
        sources=self.pipeline.model.sources
        self.check(True,self.pipeline.model.published.get(self.seed.owner.sequence) is self.seed.owner,'seed keeps its exact original published owner')
        self.check(self.seed.snapshot,sources.short_snapshot(self.seed.owner),'later positive use cannot rebase the original learning snapshot')
        tick=max(self.positive_opposed.meta_tick,*(row[2] for row in self.confirmed_increases))
        if completion_tick is not None:tick=max(tick,completion_tick)
        self.mark(EXTRA_RULES[5],tick)
        super().finish_opposition(additional_sources,completion_tick=tick)
