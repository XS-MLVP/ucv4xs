"""A correct old direction may oppose current confidence without a reread."""
from toffee import CheckContext,ScoreboardMode
from suites.frontend.bpu.bpu.checker.mixed_visibility import MixedVisibilityChecks
from suites.frontend.bpu.bpu.coverage.direction_turnaround import RULES
from suites.frontend.bpu.bpu.model.tage.direction_turnaround import PROGRAMS,CAPTURES,preparation
from suites.frontend.bpu.bpu.model.tage.dual_migration import provider,POSITIONS,TARGETS
from suites.frontend.bpu.bpu.model.tage.service import pending_plan


class DirectionTurnaroundChecks(MixedVisibilityChecks):
    programs=PROGRAMS
    rules=RULES
    capture_roles=CAPTURES
    source_profiles={'positive-interior':(5,5,(3,3)),'positive-bound':(7,5,(3,3)),
                     'negative-interior':(0,2,(0,0)),'negative-bound':(0,0,(0,0))}

    def __init__(self,pipeline,coverage,program):
        super().__init__(pipeline,coverage,program)
        self.intents=tuple(preparation())
        self.prepared_sources={}

    def check(self,expected,actual,point):
        self.raise_failure()
        try:
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(
                self.pipeline.board.name,ScoreboardMode.DIRECT,sequence_id=self.pipeline.last_tick,
                request=dict(point=point,program=self.program.name,phase=self.phase,
                    actual_accepts=self.input_ticks,actual_proposals=self.offered,
                    expected_pending=getattr(self,'expected_plan',None),
                    independent_pending=pending_plan(self.pipeline.model.sources.tage,self.table,self.bank),
                    latest_actual_state=self.last,actual_services=self.written)))
        except Exception as error:
            self.failure=error;raise

    def retain_prepared(self,role,source):
        self.check(True,role in self.capture_roles.values() and role not in self.prepared_sources,
                   'one actual source from each declared opposite prediction epoch')
        a,b,main=self.source_profiles[role]
        self.check((main,(provider(0,a),provider(1,b))),self.profile(source),
                   'opposite old confidence and complete Main/provider identities prepared normally')
        token=self.pipeline.source_token(source)
        fields=self.pipeline.model.sources.defined_metadata(token)
        for i in range(4):
            if fields.get(f'{i}.hasProvider'):
                self.check((1,0),(fields[f'{i}.useProvider'],fields[f'{i}.hasAlt']),
                           'strong original provider is independently usable without alternate reread')
        self.prepared_sources[role]=source
        self.remember(source)

    def arm_asymmetric(self,warm_source,warm_event,current):
        super().arm_asymmetric(warm_source,warm_event,current)
        self.check(set(self.capture_roles.values()),set(self.prepared_sources),'all opposite source epochs mandatory')
        original=self.read(current['original']).context
        for source in self.prepared_sources.values():
            self.check(original,self.read(source).context,'old prediction epoch still names the same logical history')
        self.saved.update(self.prepared_sources)
        self.reach(self.rules[12],sources={name:dict(meta_tick=s.meta_tick,compared=self.profile(s))
            for name,s in self.prepared_sources.items()})

    def accepted_burst(self,events):
        late=self.phase=='refill-holding'
        super().accepted_burst(events)
        if not late:return
        witnesses=[]
        for source,outcome,(tick,resolution) in zip(self.requests[3:],self.program.late_outcomes,events,strict=True):
            token=self.pipeline.source_token(source)
            branch=self.pipeline.model.sources.snapshot(token,resolved=True).late.branch
            self.check(False,any(wrong for _,_,wrong in outcome),'late reversal is correct for its genuine old prediction')
            taken=next((index for index,value,_ in outcome if value),None)
            if taken is not None:
                self.check((True,POSITIONS[taken],TARGETS[taken]),(branch.taken,branch.position,branch.target),
                           'correct old taken source is not a mislabeled new misprediction')
            else:
                end=max(POSITIONS[index] for index,_,_ in outcome)
                self.check(True,not branch.taken or branch.position>end,
                           'all supplied old-prefix branches were predicted not-taken; later outcomes stay unknown')
            witnesses.append(dict(accepted_tick=tick,meta_tick=source.meta_tick,
                                  predicted=(int(branch.kind),int(branch.taken),branch.position,branch.target),
                                  actual_prefix=outcome))
        self.reach(self.rules[13],qualified_sources=witnesses)

    def pending(self):
        late=self.phase=='refill-holding'
        super().pending()
        if late:
            self.reach(self.rules[14],original_proposals=self.expected_offers[3:],
                actual_proposals=self.offered[3:],current_results=self.expected_plan)
