"""An original S3 teacher, actual learning confirmation and a new consumer.

The pipeline scoreboard compares real outputs before calling ``checked``.
Predicted effects alone never close this lifetime or grant checked coverage.
"""
import asyncio
from copy import deepcopy
from dataclasses import asdict
from toffee import XEvent,XPhase

from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.model.late_correction_learning import program, RULES, weak_late_alternate
from suites.frontend.bpu.bpu.model.early_opposition import provider, resident
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.utage.model.semantic import Entry, tag
from suites.frontend.bpu.tage.model.semantic import HISTORIES


PHASES=('predecessor','conditional','not-taken','strengthen-negative','fallback','late-surprise')


class Checks(EarlyDirectionChecks):
    completion_rules=RULES

    def __init__(self,coverage,profile):
        self.program=program(profile)
        super().__init__(coverage,self.program.b)
        self.saved={}; self.plans={}; self.inputs=[]; self.offers={}
        self.seed=self.stable=self.weak=self.teacher=None
        self.acceptance=self.selected=self.selected_tick=None
        self.repair=self.pending=self.confirmed=self.final=None
        self.redirect_count=0; self.last_redirect=None

    def snapshots(self,token):
        sources=self.pipeline.model.sources
        return (sources.snapshot(token),sources.short_snapshot(token),sources.tage_snapshot(token),
            sources.tage_snapshot(token,resolved=True))

    def save(self,source):
        token=self.pipeline.source_token(source)
        self.check(True,self.pipeline.model.published.get(token.sequence) is token,
            'only the exact published original may own a receipt')
        self.saved.setdefault(source.meta_tick,(source,token,self.snapshots(token),deepcopy(source.meta)))
        return token

    def plan_resolution(self,phase,source):
        token=self.save(source)
        self.check(PHASES[len(self.plans)],phase,'discover and resolve the real program in order')
        self.check(self.program.resolution(phase)[0],token.pc,'original belongs to its instruction block')
        if phase in ('predecessor','conditional'):
            self.check(False,any(e.hit for row in source_entries(token.lookup) for e in row),'real cold discovery')
        if phase=='fallback':
            self.check(False,any(e.hit and e.position==4 for row in source_entries(token.lookup) for e in row),
                'later direct branch was not already present')
        self.plans[phase]=source

    def early_consumer(self,source):
        token=self.save(source); b=token.early.branch
        self.check((self.program.b,2,1,True,self.program.a),
            (token.pc,b.position,int(b.kind),b.taken,b.target),'old early conditional really selects B-to-A')
        self.check(True,token.early.source in ('ahead','ahead-direction'),'not a Main-only seed')
        self.seed=source; self.mark(RULES[1],source.meta_tick)

    def stable_predecessor(self,source):
        token=self.save(source)
        self.check((self.program.a,self.program.stable_predecessor_history),
            (token.pc,token.history.history % (1<<max(HISTORIES))),'actual steady later-path predecessor, not invented history')
        self.stable=source; self.mark(RULES[2],source.meta_tick)

    def weak_consumer(self,source):
        token=self.save(source)
        self.check(self.program.b,token.pc,'negative-control source is the same branch block')
        self.check(True,weak_late_alternate(self.pipeline.model.sources,token),
            'independent weak positive provider uses the NT alternate at S3')
        self.check(False,self.pipeline.model.control_pipe[-1][1],'early-disabled control does not claim eligible teaching')
        self.weak=source; self.mark(RULES[3],source.meta_tick)

    def open_original(self):
        self.check(None,self.acceptance,'one named original teaching window')
        self.check(True,self.seed is not None and self.stable is not None and self.weak is not None,
            'real early experience, stable path and independent late control precede issue')
        self.acceptance=asyncio.get_running_loop().create_future()
        return self.acceptance

    def candidates(self,row,events,cycle,model,phase,previous):
        self.events,self.cycle=events,cycle
        self.actual_useful=row['observed']['early_direction']['useful']
        self.applied=model.sources.short.learning
        first=cycle.tokens[0]; self.candidate=None
        if (self.acceptance is not None and not self.acceptance.done() and first is not None
                and first.pc==self.pc and cycle.fires[1] and not cycle.flushes[0]):
            values=model.sources.current_short(cycle.enabled[1]).values()
            b=cycle.decisions[0].branch
            eligible=any(values.get(f'{w}.valid') and values.get(f'{w}.position')==2
                and values.get(f'{w}.base') and not values.get(f'{w}.hit') for w in range(4))
            if (eligible and (b.position,int(b.kind),b.taken,b.target)==(2,1,True,self.program.a)
                    and weak_late_alternate(model.sources,first)):
                self.candidate=first
        return ()

    def reached(self,tick,*candidates): pass

    def checked(self,tick,*candidates):
        model=self.pipeline.model; sources=model.sources; cycle=self.cycle; events=self.events
        if self.pending is not None:
            record=self.pending
            self.check(record['written_tick']+2,tick,'exact next full actual-state comparison')
            self.check(1,self.actual_useful[0][record['index']],'actual short protection was initialized')
            self.confirmed=dict(record,actual_confirmation_tick=tick); self.pending=None
            self.mark(RULES[8],tick)
        if events.redirect is not None:
            self.redirect_count+=1; self.last_redirect=(tick,events.redirect.source,events.prediction_ready)
        if events.feedback is not None:
            request=events.feedback
            phase=next((name for name,source in self.plans.items()
                if self.pipeline.source_token(source) is request.origin),None)
            self.check(True,phase is not None,'accepted backend feedback keeps its exact declared original')
            branch,=tuple(b for b in request.branches if b is not None)
            self.check(self.program.resolution(phase),
                (request.pc,branch.position,branch.target,int(branch.kind),branch.taken,branch.mispredict),
                'complete original outcome, target and correctness')
            self.check(0,int(branch.action),'no invented return or call')
            self.check(False,events.prediction_ready,'preparation feedback is held; repair mode is tested separately')
            self.inputs.append(dict(phase=phase,owner=request.origin.sequence,tick=tick))
            self.accepted_ticks.append(tick)
            if phase=='conditional': self.mark(RULES[0],tick)
        if self.candidate is not None:
            event=self.pipeline.current_event
            self.check(True,isinstance(event,XEvent) and event.phase is XPhase.RISING_STABLE and event.tick==tick,
                'driver notification is the real already-compared monitor acceptance event')
            self.selected=self.candidate; self.selected_tick=tick
            self.acceptance.set_result(event)
        if self.selected is not None and cycle.metadata is not None and cycle.metadata.sequence==self.selected.sequence:
            token=cycle.metadata; b=cycle.decisions[2].branch
            self.check(True,token.history is self.selected.history,'S3 keeps the original S1 checkpoint')
            self.check(True,cycle.final_repair and not token.middle_corrected,'late repair, not this original S2 repair')
            self.check((2,2,4,2,True,self.program.a),
                (token.early.branch.position,token.middle.branch.position,b.position,int(b.kind),b.taken,b.target),
                'same original early/middle conditional yields to its later direct branch')
            self.check(self.program.flowing,events.prediction_ready,'held/flowing is measured at the actual S3 repair')
            saved=sources.short_snapshot(token); values=sources.defined_short_metadata(token)
            self.check(2,saved.end_position,'learning qualification ends at the original early branch')
            self.check(True,any(values.get(f'{w}.valid') and values.get(f'{w}.position')==2 for w in range(4)),
                'S3 alone does not prove original conditional learning eligibility')
            younger=tuple(t for t in cycle.tokens[:2] if t is not None)
            self.check(True,bool(younger),'the repair actually squashes a younger path')
            for young in younger:
                self.check(False,young.sequence in model.published,'squashed younger token cannot publish')
                for getter in (sources.snapshot,sources.short_snapshot,sources.tage_snapshot):
                    try: getter(young)
                    except ValueError: pass
                    else: self.check(False,True,'all younger lookup domains release their cancelled owner')
            self.repair=dict(owner=token.sequence,tick=tick,prediction_tick=self.selected_tick,
                prediction_ready=events.prediction_ready,young_S2_repair=cycle.middle_repair,
                younger=[t.sequence for t in younger],early=asdict(token.early.branch),late=asdict(b))
            for rule in RULES[4:7]: self.mark(rule,tick)
        if self.applied is not None and self.repair is not None:
            owner=self.offers.get(id(self.applied.feedback))
            if owner is not None and owner.sequence==self.repair['owner']:
                for table,index,before,after,role in sources.short.effects:
                    if table!=0 or role!='allocate': continue
                    feedback=self.applied.feedback; identity=tag(feedback.pc,feedback.context,0)
                    self.check((self.pc,4,True,2),(feedback.pc,feedback.position,feedback.taken,feedback.kind),
                        'exact original final outcome teaches the earlier conditional NT')
                    self.check(Entry(True,identity,2,3),resident(sources,(0,index)),
                        'named short allocation has independent identity and NT confidence')
                    self.pending=dict(owner=owner.sequence,index=index,tag=identity,before=before,after=after,
                        counter=3,written_tick=tick)
                    self.mark(RULES[7],tick)
        feedback=sources.last_short_events.feedback
        if feedback is not None and cycle.tokens[2] is not None:
            self.offers[id(feedback)]=cycle.tokens[2]

    def window_receipt(self,source):
        token=self.save(source)
        self.check(True,self.selected is not None and token.sequence==self.selected.sequence
            and token.history is self.selected.history and source.prediction_tick==self.selected_tick,
            'actual complete receipt belongs to the exact accepted S1 teacher')
        self.check(True,self.repair is not None and self.repair['owner']==token.sequence,'actual S3 comparison completed')
        self.teacher=source

    def negative_consumer(self,source):
        token=self.save(source); value=provider(self.pipeline.model.sources,token)
        self.check(True,self.confirmed is not None,'expected-only teaching is insufficient')
        self.check(True,value is not None and value.table==0 and value.position==2 and value.counter<4,
            'new actual short NT provider, not merely a correct Main target')
        self.check((self.confirmed['index'],self.confirmed['tag']),(value.index,value.tag),'same confirmed learned identity')
        self.check(True,source.prediction_tick>self.confirmed['actual_confirmation_tick'],'fresh query follows actual state')
        for branch in (token.early.branch,self.pipeline.model.sources.tage_snapshot(token,resolved=True).late.branch):
            self.check((4,self.program.a,2,True),(branch.position,branch.target,int(branch.kind),branch.taken),
                'early learned direction and final independent direction select the real later branch')
        self.consumer=source
        self.final=dict(owner=token.sequence,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,
            provider=asdict(value),early=asdict(token.early.branch))
        self.mark(RULES[9],source.meta_tick)

    def finish(self):
        self.check(False,self.closed,'one complete lifetime')
        self.check(PHASES,tuple(r['phase'] for r in self.inputs),'all six owned backend resolutions were accepted')
        self.check(True,all(s is not None for s in (self.seed,self.stable,self.weak,self.teacher,self.consumer)),
            'seed, stable path, weak control, original teacher and fresh consumer are all required')
        self.check(None,self.pending,'no allocation waiting for actual confirmation')
        self.check(True,self.confirmed is not None and self.final is not None and self.repair is not None,
            'all three actual evidence boundaries must exist')
        teacher=self.pipeline.source_token(self.teacher)
        self.check((teacher.sequence,teacher.sequence),(self.repair['owner'],self.confirmed['owner']),
            'young same-PC requests cannot steal original teaching ownership')
        self.check(self.confirmed['written_tick']+2,self.confirmed['actual_confirmation_tick'],'next-state evidence is retained')
        self.check(self.final['provider'],asdict(provider(self.pipeline.model.sources,self.pipeline.source_token(self.consumer))),
            'consumer report keeps its immutable provider')
        for source,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(source) is token,'receipt cannot be rebound to a copied original')
            self.check(snapshots,self.snapshots(token),'all independent original snapshot domains are immutable')
            self.check(metadata,source.meta,'full original public metadata is unchanged')
        self.mark(RULES[10],self.consumer.meta_tick)
        self.check(set(RULES),self.reached_rules,'complete original teaching obligations, not isolated event hits')
        self.check(False,self.pipeline.model.sources.main_pending(),'all declared learning matured')
        for rule in RULES: self.coverage.record('checked',rule,self.consumer.meta_tick)
        self.coverage.finish(); self.closed=True

    def snapshot(self):
        return dict(profile=self.program.name,closed=self.closed,completed=sorted(self.reached_rules),
            inputs=self.inputs,repair=self.repair,confirmed_allocation=self.confirmed,consumer=self.final,
            original_count=len(self.saved),full_FTQ_source_eligibility_proved=False,
            full_PHR_and1024protection_cells_compared=True)
