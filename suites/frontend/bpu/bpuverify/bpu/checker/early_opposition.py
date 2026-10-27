"""Associate actual opposed S3 sources to independently computed useful effects."""
from collections import deque

from bpuverify.bpu.checker.early_direction_learning import EarlyDirectionChecks
from bpuverify.bpu.coverage.early_opposition import RULES,EXTRA_RULES
from bpuverify.bpu.model.early_opposition import provider,ahead_owner,resident,main_counter,is_opposed,stable_negative,steady_history,CONDITIONAL,FALLBACK


class EarlyOppositionChecks(EarlyDirectionChecks):
    fallback_position = FALLBACK
    completion_rules=RULES

    def __init__(self,coverage,pc):
        super().__init__(coverage,pc)
        self.strong=self.positive=self.prepared=self.opposed=None
        self.protected=self.protected_entry=self.protected_useful=None
        self.base_owner=None
        self.saved_sources={}
        self.returning=False
        self.offers=deque(maxlen=8)
        self.opposed_owners=set()
        self.confirmed_increases=[]
        self.pending_effect=self.confirming=None
        self.applied=self.current_token=None
        self.direction_taken=False
        self.gain_rule=EXTRA_RULES[4]

    def save(self,source):
        token=self.pipeline.source_token(source)
        self.saved_sources[source.meta_tick]=(source,self.pipeline.model.sources.short_snapshot(token))
        return token

    def strong_negative(self,source):
        self.check(None,self.strong,'one strong independent negative provider')
        self.check(True,self.consumer is not None,'normal source discovery/learning precedes strength qualification')
        self.check(True,source.prediction_tick>self.consumer.meta_tick,'strong source is a fresh post-learning request')
        token=self.save(source);sources=self.pipeline.model.sources;value=provider(sources,token)
        self.check(True,value is not None,'real conditional provider exists')
        self.check((False,0),(value.base,value.counter),'strong negative provider with a negative base')
        self.check(True,stable_negative(sources,token),'steady provider retains the same live tag owner')
        self.protected=value.key;self.protected_entry=resident(sources,value.key)
        self.protected_useful=sources.short.useful[value.table].get(value.index,0)
        self.base_owner=ahead_owner(sources,token)[0]
        self.strong=source;self.mark(EXTRA_RULES[0],source.meta_tick)

    def positive_base(self,source):
        self.check(True,self.strong is not None,'preserve the negative provider before biasing the base')
        self.check(None,self.positive,'one positive base alias')
        self.check(True,source.prediction_tick>self.strong.meta_tick,'positive alias uses a fresh source')
        token=self.save(source);sources=self.pipeline.model.sources
        self.check(3,main_counter(token),'Main positive counter reached by ordinary resolves')
        self.check(True,steady_history(token,CONDITIONAL),'positive path has its own stable history, not a transient alias')
        self.check((self.base_owner,3),ahead_owner(sources,token),'same complete Ahead owner becomes strong taken')
        frame=sources.short_snapshot(token).prediction.frame
        self.check(True,frame is not None and frame.read.indices[self.protected[0]]!=self.protected[1],
            'different owned MicroTAGE index, not another physical sweep coordinate')
        self.check(self.protected_entry,resident(sources,self.protected),'other-history bias cannot rebase protected provider')
        self.check(self.protected_useful,sources.short.useful[self.protected[0]].get(self.protected[1],0),
            'protected usefulness is unchanged while biasing the base')
        self.positive=source;self.mark(EXTRA_RULES[1],source.meta_tick)

    def main_negative(self,source):
        self.check(True,self.positive is not None,'base was independently biased before Main changes')
        self.check(None,self.prepared,'one pre-return Main state')
        self.check(True,source.prediction_tick>self.positive.meta_tick,'Main-only preparation has a fresh source')
        token=self.save(source);sources=self.pipeline.model.sources
        self.check(0,main_counter(token),'Main alone becomes strong not-taken')
        self.check(True,steady_history(token,FALLBACK),'new Main-only fallback path has stable independent history')
        self.check(False,sources.snapshot(token).enabled,'ordinary Main updates occur with fast learners disabled')
        self.check(3,sources.ahead.counters[self.base_owner],'Ahead keeps its positive bias')
        self.check(self.protected_entry,resident(sources,self.protected),'Main-only preparation preserves protected provider')
        self.check(self.protected_useful,sources.short.useful[self.protected[0]].get(self.protected[1],0),'Main-only preparation preserves useful')
        self.prepared=source;self.returning=True;self.mark(EXTRA_RULES[2],source.meta_tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        result=super().candidates(row,events,cycle,model,phase,previous)
        self.current_token=cycle.metadata
        self.applied=model.sources.short.learning
        self.confirming=self.pending_effect
        if self.confirming is not None:
            _,_,table,index,before,after=self.confirming
            self.check(after,model.sources.short.useful[table].get(index,0),'predicted effect is at the next actual-state comparison boundary')
        return result

    def qualifies_current_source(self,sources,token):
        return is_opposed(sources,token,taken=self.direction_taken)

    def tracks_useful_key(self,key):return key==self.protected

    def checked(self,tick,*candidates):
        super().checked(tick,*candidates)
        sources=self.pipeline.model.sources
        # This follows the complete BEFORE-advance useful-state comparison.
        # A freshly computed model effect is not credit until the next sample.
        if self.confirming is not None:
            owner,written,table,index,before,after=self.confirming
            self.check(written+2,tick,'lossless next-boundary useful confirmation')
            self.confirmed_increases.append((owner.sequence,written,tick,before,after))
            self.mark(self.gain_rule,tick)
        self.pending_effect=None
        token=self.current_token
        if self.returning and token is not None and token.pc==self.pc and self.qualifies_current_source(sources,token):
            self.opposed_owners.add(token.sequence)
        if self.applied is not None:
            owner=next((owner for feedback,owner in self.offers if feedback is self.applied.feedback),None)
            for table,index,before,after,role in sources.short.effects:
                if (role=='useful-increase' and after>before and self.tracks_useful_key((table,index))
                        and owner is not None and owner.sequence in self.opposed_owners):
                    self.pending_effect=(owner,tick,table,index,before,after)
        feedback=sources.last_short_events.feedback
        if feedback is not None and token is not None:self.offers.append((feedback,token))

    def opposed_consumer(self,source):
        self.check(True,self.prepared is not None,'opposition follows independent preparation')
        self.check(None,self.opposed,'one named opposed consumer')
        self.check(True,source.prediction_tick>self.prepared.meta_tick,'opposed consumer follows Main-only preparation')
        token=self.save(source);sources=self.pipeline.model.sources
        value=provider(sources,token)
        self.check(True,is_opposed(sources,token),'valid NT provider must disagree with positive Ahead base')
        self.check(self.protected,value.key,'consume the protected independent provider')
        self.check((FALLBACK,self.pc,True,2,'ahead-direction'),
            (token.early.branch.position,token.early.branch.target,token.early.branch.taken,
                int(token.early.branch.kind),token.early.source),'provider suppresses earlier conditional and chooses later direct jump')
        self.check((),self.pipeline.corrections_for_source(source),'new opposed S1 already agrees with independently owned Main')
        self.check(True,token.sequence in self.opposed_owners,'complete coherent S3 comparison precedes consumer credit')
        self.opposed=source;self.mark(EXTRA_RULES[3],source.meta_tick)

    def finish_opposition(self,additional_sources=(),*,completion_tick=None):
        self.check(True,self.opposed is not None,'actual new opposed receipt is required')
        self.check(True,bool(self.confirmed_increases),'an opposed original S3 source must cause a physically confirmed useful increase')
        self.check(None,self.pending_effect,'all claimed useful effects have crossed an actual comparison boundary')
        for source,snapshot in self.saved_sources.values():
            token=self.pipeline.source_token(source)
            self.check(snapshot,self.pipeline.model.sources.short_snapshot(token),'opposed snapshots remain immutable across later updates')
        tick=max(self.opposed.meta_tick,*(row[2] for row in self.confirmed_increases))
        if completion_tick is not None:tick=max(tick,completion_tick)
        self.mark(EXTRA_RULES[5],tick)
        super().finish(completion_tick=tick)
        # Parent closure releases its four named discovery/learning owners.
        # Extra preparation owners remain distinct, despite equal PC encodings.
        for source in {source.meta_tick:source for source in additional_sources}.values():
            if source.meta_tick in self.pipeline.source_receipts:self.pipeline.retire_source(source.meta_tick)
