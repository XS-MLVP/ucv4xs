"""Different-age corrections keep independent owners and restore only the winner."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
from toffee import XEvent,XPhase
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.model.competing_correction import program,RULES,PHASES,restored
from suites.frontend.bpu.bpu.model.late_correction_learning import weak_late_alternate
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.early_opposition import resident
from suites.frontend.bpu.utage.model.semantic import Entry,tag


class Checks(EarlyDirectionChecks):
    completion_rules=RULES
    def __init__(self,coverage,profile):
        self.program=program(profile); super().__init__(coverage,self.program.b)
        self.saved={}; self.plans={}; self.inputs=[]; self.offers={}; self.phase='setup'
        self.seed=self.weak=self.stable=self.prepared=self.selected=self.young=None
        self.preparation=self.release=None; self.prepared_tick=self.selected_tick=None
        self.repair=self.restore_pending=self.restoration=self.pending=self.confirmed=self.final=None
        self.redirect_count=0; self.last_redirect=None

    def snapshots(self,token):
        s=self.pipeline.model.sources
        return s.snapshot(token),s.short_snapshot(token),s.tage_snapshot(token),s.tage_snapshot(token,resolved=True)

    def save(self,source):
        token=self.pipeline.source_token(source)
        self.check(True,self.pipeline.model.published.get(token.sequence) is token,'exact published original required')
        self.saved.setdefault(source.meta_tick,(source,token,self.snapshots(token),deepcopy(source.meta)))
        return token

    def plan_resolution(self,phase,source):
        token=self.save(source)
        self.check(PHASES[len(self.plans)],phase,'real discoveries and outcomes are declared in order')
        self.check(self.program.resolution(phase)[0],token.pc,'instruction belongs to its real block')
        if phase in ('predecessor','conditional'):
            self.check(False,any(e.hit for row in source_entries(token.lookup) for e in row),'genuine cold source')
        if phase=='young-discovery':
            self.check('held',self.phase,'new young branch is learned while the old lookup is held')
            self.check(False,any(e.hit and e.position==3 for row in source_entries(token.lookup) for e in row),
                'new conditional genuinely absent from original A')
        self.plans[phase]=source

    def early_consumer(self,source):
        token=self.save(source); b=token.early.branch
        self.check((self.pc,2,1,True,self.program.a),(token.pc,b.position,int(b.kind),b.taken,b.target),
            'real old early B conditional experience')
        self.seed=source

    def stable_predecessor(self,source): self.stable=source; self.save(source)

    def weak_consumer(self,source):
        token=self.save(source)
        self.check(True,weak_late_alternate(self.pipeline.model.sources,token),'independent weak T provider has NT late alternate')
        self.weak=source
        self.check(True,self.seed is not None and self.stable is not None,'old early experience and real steady predecessor required')
        self.mark(RULES[0],source.meta_tick)

    def open_preparation(self):
        self.check('setup',self.phase,'one preparation window')
        self.check(True,self.weak is not None,'independent late control precedes holding its next lookup')
        self.phase='preparing'; self.preparation=asyncio.get_running_loop().create_future(); return self.preparation

    def open_release(self):
        self.check('held',self.phase,'qualified old lookup has been held')
        self.check('young-discovery',self.inputs[-1]['phase'],'new young branch actually accepted before release')
        self.phase='release'; self.release=asyncio.get_running_loop().create_future(); return self.release

    def notify(self,future,tick):
        event=self.pipeline.current_event
        self.check(True,isinstance(event,XEvent) and event.phase is XPhase.RISING_STABLE and event.tick==tick,
            'only a real compared monitor event terminates a driver window')
        future.set_result(event)

    def candidates(self,row,events,cycle,model,phase,previous):
        self.events,self.cycle=events,cycle
        self.applied=model.sources.short.learning; self.actual_useful=row['observed']['early_direction']['useful']
        return ()

    def reached(self,tick,*candidates): pass

    def checked(self,tick,*candidates):
        model=self.pipeline.model; s=model.sources; cycle=self.cycle; events=self.events; p=self.program
        if self.restore_pending is not None:
            old=self.restore_pending; first=cycle.tokens[0]
            self.check(old['tick']+2,tick,'next complete actual comparison confirms restoration')
            self.check(True,first is not None and first.history.history==old['winning_history'] and first.pc==p.a,
                'new lookup carries only the old S3 winning history')
            self.restoration=dict(old,actual_confirmation_tick=tick,new_owner=first.sequence); self.restore_pending=None
            self.mark(RULES[8],tick)
        if self.pending is not None:
            old=self.pending
            self.check(old['written_tick']+2,tick,'learning has the exact next actual-state comparison')
            self.check(1,self.actual_useful[0][old['index']],'old original protection actually initialized')
            self.confirmed=dict(old,actual_confirmation_tick=tick); self.pending=None; self.mark(RULES[10],tick)
        if events.redirect is not None:
            self.redirect_count+=1; self.last_redirect=tick,events.redirect.source,events.prediction_ready
        if self.phase=='held':
            self.check(True,cycle.tokens[0] is self.prepared and not cycle.fires[1],
                'held original survives real preparation without being silently consumed')
        if events.feedback is not None:
            r=events.feedback; phase=next((name for name,source in self.plans.items()
                if self.pipeline.source_token(source) is r.origin),None)
            self.check(True,phase is not None,'every real input has one exact original')
            b,=tuple(b for b in r.branches if b is not None)
            self.check(p.resolution(phase),(r.pc,b.position,b.target,int(b.kind),b.taken,b.mispredict),'full resolved branch semantics')
            self.check(False,events.prediction_ready,'preparation learning is held, not a fixed delay')
            self.inputs.append(dict(phase=phase,owner=r.origin.sequence,tick=tick)); self.accepted_ticks.append(tick)
            if phase=='young-discovery': self.mark(RULES[2],tick)
        first=cycle.tokens[0]
        if self.phase=='preparing' and cycle.fires[0] and cycle.fires[1] and not cycle.flushes[0] and first.pc==p.a:
            candidate=model.stages[0]
            if candidate is not None and candidate.pc==p.b:
                early=s.choose(candidate,1,cycle.enabled).branch; values=s.current_short(cycle.enabled[1]).values()
                eligible=any(values.get(f'{w}.valid') and values.get(f'{w}.position')==2 and values.get(f'{w}.base')
                    and not values.get(f'{w}.hit') for w in range(4))
                if eligible and early.position==2 and early.taken and weak_late_alternate(s,candidate):
                    self.prepared=candidate; self.prepared_tick=tick; self.phase='held'
                    self.notify(self.preparation,tick); self.mark(RULES[1],tick)
        if self.phase=='release' and first is not None and cycle.fires[1] and not cycle.flushes[0]:
            if self.selected is None:
                self.check(True,first is self.prepared,'release consumes the exact previously held old lookup')
                self.selected=first; self.selected_tick=tick; self.mark(RULES[3],tick)
            elif self.young is None:
                b=cycle.decisions[0].branch
                self.check((p.a,6,2,True,p.b),(first.pc,b.position,int(b.kind),b.taken,b.target),
                    'young path retains its old later-direct early experience')
                self.young=first; self.notify(self.release,tick); self.phase='competing'; self.mark(RULES[4],tick)
        if self.selected is not None and cycle.metadata is not None and cycle.metadata.sequence==self.selected.sequence:
            old,young=cycle.tokens[2],cycle.tokens[1]; late,middle=cycle.decisions[2].branch,cycle.decisions[1].branch
            self.check(True,cycle.final_repair and cycle.middle_repair,'both real corrections occur in the same actual boundary')
            self.check(False,old.middle_corrected,'old request itself was not already corrected in S2')
            self.check(True,young is not None and self.young is not None and young.history is self.young.history,
                'young S2 correction is the exact independently accepted A original')
            self.check((p.b,4,2,True,p.a,p.a,3,1,True,p.b),
                (old.pc,late.position,int(late.kind),late.taken,late.target,young.pc,middle.position,int(middle.kind),middle.taken,middle.target),
                'different actual instruction positions and targets cannot collapse to one recovery')
            winner,loser=restored(old,late),restored(young,middle)
            self.check(False,winner==loser,'old and young candidate histories are observably different')
            self.check((p.a,winner),(cycle.next_pc,model.stages[0].history.history),'old path wins both target and complete history')
            self.check(p.flowing,events.prediction_ready,'actual held/flowing state at competing correction')
            for cancelled in (t for t in cycle.tokens[:2] if t is not None):
                self.check(False,cancelled.sequence in model.published,'cancelled younger source does not publish')
                for getter in (s.snapshot,s.short_snapshot,s.tage_snapshot):
                    try:getter(cancelled)
                    except ValueError:pass
                    else:self.check(False,True,'cancelled lookup cannot borrow any component snapshot')
            self.repair=dict(owner=old.sequence,young_owner=young.sequence,tick=tick,prediction_ready=events.prediction_ready,
                winning_history=winner,rejected_history=loser,old_branch=asdict(late),young_branch=asdict(middle),
                prediction_tick=self.selected_tick)
            self.restore_pending=self.repair
            for rule in RULES[5:8]:self.mark(rule,tick)
        if self.applied is not None and self.repair is not None:
            owner=self.offers.get(id(self.applied.feedback))
            if owner is not None and owner.sequence==self.repair['owner']:
                for table,index,before,after,role in s.short.effects:
                    if table!=0 or role!='allocate':continue
                    feedback=self.applied.feedback; identity=tag(feedback.pc,feedback.context,0)
                    self.check(Entry(True,identity,2,3),resident(s,(0,index)),'winning old conditional still learns NT independently')
                    self.pending=dict(owner=owner.sequence,index=index,tag=identity,written_tick=tick,before=before,after=after,counter=3)
                    self.mark(RULES[9],tick)
        feedback=s.last_short_events.feedback
        if feedback is not None and cycle.tokens[2] is not None:self.offers[id(feedback)]=cycle.tokens[2]

    def consume_restored(self,source):
        token=self.save(source)
        self.check(True,self.restoration is not None and self.confirmed is not None,'actual restoration and original learning confirmed first')
        self.check((self.program.a,self.repair['winning_history']),(token.pc,token.history.history),
            'new complete public source owns the winning original history, not the young candidate')
        self.check(self.restoration['new_owner'],token.sequence,'consumer is the exact restored lookup, not a later equal history')
        self.check(True,source.prediction_tick>self.repair['tick'],'real new post-correction acceptance')
        self.check((3,self.program.b,1,True),(token.middle.branch.position,token.middle.branch.target,
            int(token.middle.branch.kind),token.middle.branch.taken),'restored lookup consumes newly learned A branch independently')
        self.consumer=source; self.final=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            pc=token.pc,history=token.history.history,middle=asdict(token.middle.branch))
        self.mark(RULES[11],source.meta_tick)

    def finish(self):
        self.check(False,self.closed,'one atomic original recovery lifetime')
        self.check(PHASES,tuple(r['phase'] for r in self.inputs),'all seven real original resolutions accepted')
        self.check(True,self.consumer is not None and self.repair is not None and self.restoration is not None and self.confirmed is not None,
            'actual competition, restored state, old learning and fresh public consumer all required')
        self.check(None,self.restore_pending,'no predicted-only restoration'); self.check(None,self.pending,'no predicted-only learning')
        self.check(self.repair['owner'],self.confirmed['owner'],'young request cannot steal old learning ownership')
        self.check(self.repair['winning_history'],self.restoration['winning_history'],'restoration report keeps the winning original history')
        self.check(self.repair['tick']+2,self.restoration['actual_confirmation_tick'],'next actual restoration boundary is retained')
        self.check(self.confirmed['written_tick']+2,self.confirmed['actual_confirmation_tick'],'next actual learning boundary is retained')
        self.check(self.repair['winning_history'],self.final['history'],'consumer report cannot substitute the rejected young history')
        self.check(self.restoration['new_owner'],self.final['owner'],'consumer report retains the exact restored lookup identity')
        for source,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(source) is token,'original receipt remains exact')
            self.check(snapshots,self.snapshots(token),'every original component snapshot remains immutable')
            self.check(metadata,source.meta,'complete original public metadata is immutable')
        self.mark(RULES[12],self.consumer.meta_tick)
        self.check(set(RULES),self.reached_rules,'complete original recovery obligations')
        self.check(False,self.pipeline.model.sources.main_pending(),'all logical learning mature')
        for rule in RULES:self.coverage.record('checked',rule,self.consumer.meta_tick)
        self.coverage.finish();self.closed=True

    def snapshot(self):
        return dict(profile=self.program.name,closed=self.closed,completed=sorted(self.reached_rules),inputs=self.inputs,
            repair=self.repair,restoration=self.restoration,confirmed_learning=self.confirmed,consumer=self.final,
            prepared_owner=None if self.prepared is None else self.prepared.sequence,prepared_tick=self.prepared_tick,
            old_lookup_survived_young_discovery=True if self.repair is not None else False,
            original_count=len(self.saved),full_PHR_and1024protection_cells_compared=True,full_FTQ_source_eligibility_proved=False)
