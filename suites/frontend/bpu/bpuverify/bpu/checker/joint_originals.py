"""Associate overlapping independent learning stages with accepted originals."""
from copy import deepcopy
from bpuverify.bpu.checker.joint_direction_learning import Checks as JointChecks
from bpuverify.bpu.checker.sc_loop_experience import Checks as LoopChecks
from bpuverify.bpu.checker.statistical_prefix import Checks as PrefixChecks
from bpuverify.bpu.checker.statistical import signed_value
from bpuverify.bpu.model.joint_originals import Program,RULES
from bpuverify.bpu.model.joint_direction_learning import tage_offer_values
from bpuverify.bpu.model.pipeline import Resolution
from bpuverify.bpu.bundle.tage_semantic import HISTORY_PORTS
from bpuverify.sc.model.semantic import Context,coordinates,feedback_needs_read


class Checks(JointChecks):
    program_type=Program

    def __init__(self,profile,coverage):
        super().__init__(profile,coverage)
        self.many=None;self.accepted_order=[];self.overlaps=[];self.phase='prepare'
        self.preparation=set()

    def mark(self,rule):
        if rule in ('valid-nonzero-original','owned-five-family-read','cold-unused-control'):
            # Reused setup proves one old source, not the new two-owner point.
            self.check('prepare',self.phase,'single-source preparation cannot award two-original coverage')
            self.preparation.add(rule)
            return
        PrefixChecks.mark(self,rule)

    def provider(self,receipt,iteration=None):
        token,value=self.source(receipt,self.program.old_iteration if iteration is None else iteration)
        slot,=[i for i,b in enumerate(value.branches) if b is not None and b.position==self.program.position]
        fields=dict(self.bank.tage_snapshot(token,resolved=True).wanted)
        self.check((True,self.expected_provider),(bool(fields[f'{slot}.has_provider']),fields[f'{slot}.counter']),
            'fresh real loop source consumes independently learned direction confidence')
        return slot,value

    def begin_many(self,sources):
        self.phase='learning';self.check(None,self.many,'one declared two-original lifecycle')
        p=self.program;by_age=[]
        for source,iteration,taken in zip(sources,p.iterations,p.truths,strict=True):
            token,value=self.source(source,iteration)
            slot,_=self.provider(source,iteration)
            self.check(0,value.prediction.used[slot],'both originals genuinely require learning, not a fabricated qualification')
            resolution=Resolution(token.history,token.pc,(p.outcome(token,value.late,taken),),origin=token)
            tx=self.bank.sc_feedback(resolution,True)
            self.check(True,feedback_needs_read(tx),'each original independently requires all five learning reads')
            p.require_feedback_window(self.pipeline.model.history.taken_edges,token.history.taken_edges)
            by_age.append(dict(source=token,receipt=source,iteration=iteration,taken=taken,resolution=resolution,
                accepted=None,history_windows=[],payload=None,read=None,SC_offers=[],TAGE_offers=[]))
        self.many=[by_age[i] for i in p.arrival_order]
        self.check(2,len({r['source'].sequence for r in self.many}),'two distinct genuine prediction owners')
        for rule in ('valid-nonzero-originals','distinct-adjacent-iterations','original-qualification'):self.mark(rule)

    def candidates(self,row,*args):
        LoopChecks.candidates(self,row,*args)
        self.actual_tage=deepcopy(row['observed']['joint_tage'])
        self.SC_offer_owner=None
        if self.many is None:return ()
        if self.expected_patches:
            tx=self.bank.sc.learning[0]
            matches=[r for r in self.many if r.get('_SC') is tx]
            self.check(1,len(matches),'SC learning stage retains one previously accepted owner')
            self.SC_offer_owner=matches[0]
        if self.training['valid']:
            pending=[r for r in self.many if r['accepted'] is None]
            self.check(True,bool(pending),'every proposal belongs to a not-yet-accepted original')
            row_owner=pending[0];token=row_owner['source']
            age=self.program.require_feedback_window(self.pipeline.model.history.taken_edges,token.history.taken_edges)
            expected=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
            self.check(expected,self.observed['joint_train_folds'],'actual training history remains the live proposed original')
            row_owner['history_windows'].append(dict(tick=self.pipeline.current_event.tick,displacement_bits=age,
                actual_folds_compared=True))
            payload={k:deepcopy(v) for k,v in self.training.items() if k not in ('valid','ready')}
            if row_owner['payload'] is None:row_owner['payload']=payload
            self.check(row_owner['payload'],payload,'every held original retains its complete unmodified payload')
        return ()

    def checked(self,tick,*args):
        PrefixChecks.checked(self,tick,*args)
        if self.many is None:return
        request=self.events.feedback
        if request is not None:
            pending=[r for r in self.many if r['accepted'] is None];self.check(True,bool(pending),'no extra acceptance')
            owner=pending[0]
            self.check(True,request.origin is owner['source'],'actual acceptance follows submitted original identity')
            self.check(owner['resolution'].branches,tuple(b for b in request.branches if b is not None),'each original keeps its declared execution truth')
            self.check((True,True),(bool(self.cycle.enabled[2] and self.cycle.enabled[3]),
                bool(self.cycle.enabled[2] and self.cycle.enabled[4])),'both direction and correction learn at every core acceptance')
            owner['accepted']=tick;self.accepted_order.append(owner['source'].sequence)
            owner['_TAGE']=self.bank.tage.accepted.feedback
            owner['_SC'],read=self.bank.sc.learning
            self.check(self.bank.feedback_for(owner['resolution']),owner['_TAGE'],'direction learner receives the same independently owned original')
            self.check(self.bank.sc_feedback(owner['resolution'],True),owner['_SC'],'correction learner receives that original, not a neighbor')
            context=Context.from_history(owner['_SC'].history);bank,indices=coordinates(request.pc,context)
            self.check(owner['iteration'],context.loop,'accepted training retains the original iteration')
            ports=self.observed['statistical']['accepted_reads']
            self.check(tuple(dict(valid=1,index=index,bank=1<<bank) for index in indices),ports,'all actual training reads name the independently owned context')
            actual=tuple(tuple(signed_value(v,6) for v in values) for values in self.observed['joint_SC_train_words'])
            self.check(read.weights,actual,'all 32 actual training-read weights match this accepted read view')
            self.check(self.program.training_weights(owner['iteration']),read.weights,
                'overlapping originals actually read their declared cold or independently prelearned experience')
            owner['read']=dict(tick=tick,indices=indices,expected=read.weights,actual=actual)
        if self.expected_patches:
            owner=self.SC_offer_owner
            self.check(True,owner['accepted'] is not None,'SC effect cannot precede its actual acceptance')
            self.check(tuple(range(5)),tuple(v[0] for v in self.expected_patches),'this original owns a complete five-family effect')
            for table,bank,index,patch in self.expected_patches:
                port=self.observed['statistical']['updates'][table]
                e=dict(valid=True,index=index,bank=1<<bank,mask=tuple(v is not None for v in patch),
                    data={str(i):v for i,v in enumerate(patch) if v is not None})
                a=dict(valid=bool(port['valid']),index=port['index'],bank=port['bank'],mask=tuple(map(bool,port['mask'])),
                    data={str(i):signed_value(port['data'][i],6) for i,v in enumerate(patch) if v is not None})
                self.check(e,a,'each complete actual SC update belongs to the scheduled original')
            owner['SC_offers'].append(dict(tick=tick,patches=deepcopy(self.expected_patches)))
        writes,useful,start=self.bank.tage.preview_learning()
        expected,actual=tage_offer_values(writes,useful,self.actual_tage)
        self.check(expected,actual,'complete actual direction effects, including every invalid table, match independent learning')
        if writes or useful:
            tx=self.bank.tage.mature.feedback
            matches=[r for r in self.many if r.get('_TAGE') is tx]
            self.check(1,len(matches),'direction learning stage retains one exact accepted original')
            owner=matches[0];self.check(True,owner['accepted'] is not None,'direction effect cannot precede acceptance')
            self.check(False,start,'bounded two-result program cannot silently start unrelated aging')
            owner['TAGE_offers'].append(dict(tick=tick,expected=expected,actual=actual))

    def end_many(self,accepted):
        self.check(tuple(r['accepted'] for r in self.many),tuple(v.tick for v in accepted),'driver completions equal actual monitor acceptances')
        self.check(tuple(r['source'].sequence for r in self.many),tuple(self.accepted_order),'submitted order is independent of original age order')
        for r in self.many:
            self.check((1,1,True),(len(r['SC_offers']),len(r['TAGE_offers']),r['read'] is not None),
                'each accepted original completes both full effects once')
            self.check(True,bool(r['history_windows']),'actual original history was compared before acceptance')
        first,second=self.many
        bound=max(first['SC_offers'][0]['tick'],first['TAGE_offers'][0]['tick'])
        self.check(True,first['accepted']<second['accepted']<=bound,
            'the second actual acceptance overlaps the first actual learning effect, not just Python tasks')
        self.overlaps.append(dict(first=first['source'].sequence,second=second['source'].sequence,
            first_accept=first['accepted'],second_accept=second['accepted'],first_effect_end=bound))
        for rule in ('live-original-history','one-acceptance-per-original','both-learners-enabled','actual-learning-overlap',
            'complete-TAGE-effects','complete-five-family-effects','submitted-order-preserved','shared-read-view','no-effect-before-acceptance'):self.mark(rule)
        self.phase='consumption'

    def finish_many(self,fresh):
        self.check({'valid-nonzero-original','owned-five-family-read','cold-unused-control'},self.preparation,
            'all reused setup checks completed without being counted as two-owner credit')
        self.check(2,len(self.consumers),'both original iterations have new numeric consumers')
        for row in self.consumers:
            self.check(self.program.expected_weights(row['iteration']),row['weights'],
                'shared experience follows its read view while each original keeps its private result')
        self.mark('private-experience-independent');self.mark('fresh-consumers')
        result=PrefixChecks.finish(self,fresh);self.phase='qualified'
        return dict(result,**self.summary(),status='PASS')

    def summary(self):
        public=[]
        for r in self.many or ():
            public.append(dict(owner=r['source'].sequence,iteration=r['iteration'],taken=r['taken'],accepted=r['accepted'],
                history_windows=deepcopy(r['history_windows']),training_read=deepcopy(r['read']),
                SC_offers=deepcopy(r['SC_offers']),TAGE_offers=deepcopy(r['TAGE_offers'])))
        return dict(LoopChecks.summary(self),phase=self.phase,preparation_checks=sorted(self.preparation),
            joint_originals=public,learning_overlap=deepcopy(self.overlaps))
