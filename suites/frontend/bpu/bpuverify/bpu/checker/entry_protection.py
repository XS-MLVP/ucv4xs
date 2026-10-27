"""Pair each actual short protection change with its exact public original."""
from dataclasses import asdict
from bpuverify.bpu.checker.early_opposition import EarlyOppositionChecks
from bpuverify.bpu.model.entry_protection import program,rules,COMMON,LOSS
from bpuverify.bpu.model.early_opposition import provider,main_counter


class Checks(EarlyOppositionChecks):
    def before_flowing_recovery(self,source):
        """Optional original-source association before driver admission."""
        return None

    def __init__(self,coverage,profile):
        self.program=program(profile); self.completion_rules=rules(profile)
        super().__init__(coverage,self.program.pc)
        self.redirect_count=0; self.last_redirect=None; self.redirect_source=None
        self.pending_loss=None; self.losses=[]; self.reward=None; self.wrong=None; self.wrong_source=None; self.final=None

    def strong_negative(self,source):
        super().strong_negative(source)
        token=self.pipeline.source_token(source); value=provider(self.pipeline.model.sources,token)
        self.check((self.pc,0,2),(token.pc,value.table,value.position),'actual interior short original, not another long provider')
        self.mark(COMMON[0],source.meta_tick)

    def candidates(self,row,events,cycle,model,phase,previous):
        self.redirect_source=None if events.redirect is None else events.redirect.source
        self.redirect_ready=events.prediction_ready
        self.loss_confirmation=self.pending_loss
        self.actual_useful=row['observed']['early_direction']['useful']
        return super().candidates(row,events,cycle,model,phase,previous)

    def checked(self,tick,*candidates):
        super().checked(tick,*candidates)
        if self.redirect_source is not None:
            self.redirect_count+=1; self.last_redirect=tick,self.redirect_source,self.redirect_ready
        if self.loss_confirmation is not None:
            receipt=self.loss_confirmation
            self.check(receipt['written_tick']+2,tick,'loss crosses the next full actual comparison')
            table,index=receipt['key']; self.check(receipt['after'],self.actual_useful[table][index],
                'actual short protection, not a predicted model write')
            self.losses.append(dict(receipt,actual_confirmation_tick=tick))
        self.pending_loss=None
        if self.applied is None or self.protected is None: return
        owner=next((owner for feedback,owner in self.offers if feedback is self.applied.feedback),None)
        for table,index,before,after,role in self.pipeline.model.sources.short.effects:
            if role!='useful-decrease' or after>=before or (table,index)!=self.protected: continue
            self.check(True,owner is not None and self.pipeline.model.published.get(owner.sequence) is owner,
                'original published S3 owns the actual penalty')
            value=provider(self.pipeline.model.sources,owner); feedback=self.applied.feedback
            self.check(True,value is not None and value.key==self.protected and value.counter<4,
                'penalty remains on the original NT short record')
            self.check((2,True,1),(feedback.position,feedback.taken,feedback.kind),'original NT is wrong, not reclassified from current direction')
            self.pending_loss=dict(owner=owner.sequence,key=self.protected,before=before,after=after,
                written_tick=tick,original_provider=asdict(value))

    def reward_receipt(self,source):
        token=self.save(source)
        matches=[r for r in self.confirmed_increases if r[0]==token.sequence]
        self.check(True,bool(matches),'named public original itself owns a physically confirmed reward')
        owner,written,actual,before,after=matches[0]
        self.check(True,source.meta_tick<written<actual and actual==written+2 and after==before+1,
            'complete reward response/effect/actual comparison chain')
        self.reward=dict(owner=owner,written_tick=written,actual_confirmation_tick=actual,before=before,after=after,
            original_provider=asdict(provider(self.pipeline.model.sources,token)))
        self.mark(COMMON[1],actual)

    def wrong_receipt(self,source):
        token=self.save(source); value=provider(self.pipeline.model.sources,token)
        self.check(True,value is not None,'wrong receipt retains an original qualified provider')
        self.check((self.pc,self.protected,False),(token.pc,value.key,value.base),'same original interior NT agrees with base but is wrong')
        self.check((2,self.pc,True,3),(token.middle.branch.position,token.middle.branch.target,token.middle.branch.taken,main_counter(token)),
            'independently trained Main contradicts the original NT direction')
        matches=[r for r in self.losses if r['owner']==token.sequence]
        self.check(True,bool(matches),'named wrong public original itself owns actual protection loss')
        loss=matches[0]
        self.check(True,source.meta_tick<loss['written_tick']<loss['actual_confirmation_tick'],'wrong response precedes its actual loss')
        self.wrong=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),loss=loss)
        self.wrong_source=source
        self.mark(LOSS[0],source.meta_tick); self.mark(LOSS[1],loss['actual_confirmation_tick'])
        self.mark(LOSS[2],loss['actual_confirmation_tick'])

    def final_source(self,source):
        token=self.save(source); boundary=self.reward['actual_confirmation_tick'] if self.wrong is None else self.wrong['loss']['actual_confirmation_tick']
        self.check(True,source.prediction_tick>boundary,'fresh exact-level source after actual protection comparison')
        branch=token.middle.branch; position=4 if self.program.mode=='contribution' else 2
        self.check((self.pc,position,self.pc,True),(token.pc,branch.position,branch.target,branch.taken),'complete post-effect public prediction')
        self.final=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            exact=asdict(branch),short_reconsumption_proved=False)
        self.mark(COMMON[2],source.meta_tick)

    def finish_opposition(self,additional_sources=(),*,completion_tick=None):
        self.check(True,self.reward is not None and self.final is not None,'actual reward and later source required')
        self.check(None,self.pending_loss,'no unconfirmed actual loss')
        self.check(self.program.mode=='contradiction',self.wrong is not None,'declared contradiction profile has its actual owned loss')
        owner=self.pipeline.source_token(self.opposed)
        self.check(owner.sequence,self.reward['owner'],'reward keeps the named original at final closure')
        receipt=tuple(self.reward[k] for k in ('owner','written_tick','actual_confirmation_tick','before','after'))
        self.check(True,receipt in self.confirmed_increases,'reward is still the complete actually confirmed receipt')
        if self.wrong is not None:
            self.check(True,self.wrong_source is not None,'wrong receipt keeps its original source')
            self.check(self.pipeline.source_token(self.wrong_source).sequence,self.wrong['owner'],'penalty original cannot be rebound at closure')
            self.check(self.wrong['owner'],self.wrong['loss']['owner'],'loss belongs to the same wrong original')
            self.check(True,self.wrong['loss'] in self.losses,'loss retains its actual next-boundary receipt')
        super().finish_opposition(additional_sources,completion_tick=self.final['meta_tick'])

    def snapshot(self):
        return dict(profile=self.program.name,closed=self.closed,protected=self.protected,reward=self.reward,
            wrong=self.wrong,final=self.final,losses=self.losses,completed=sorted(self.reached_rules),
            full_FTQ_source_eligibility_proved=False,new_short_direction_consumer_proved=False)
