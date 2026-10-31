"""Complete original-prefix qualification and two actual learning boundaries."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.opposed_learning_pair import OpposedLearningPairChecks
from suites.frontend.bpu.bpu.coverage.interior_prefix_learning import RULES
from suites.frontend.bpu.bpu.model.tage.interior_prefix_learning import PROGRAMS,NEGATIVE,SOURCE_CAPTURES,preparation
from suites.frontend.bpu.bpu.model.tage.service import pending_plan,learning_inflight


class Checks(OpposedLearningPairChecks):
    programs=PROGRAMS
    rules=RULES
    capture_roles=SOURCE_CAPTURES
    before_capture_roles={'negative-epoch-3':NEGATIVE}
    source_profiles=dict(OpposedLearningPairChecks.source_profiles,**{NEGATIVE:(2,2,(0,0))})

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.intents=tuple(preparation());self.first_settled=None;self.interior_source=None

    def retain_prepared(self,role,source):
        super().retain_prepared(role,source)
        if role==NEGATIVE:
            self.interior_source=dict(meta_tick=source.meta_tick,profile=deepcopy(self.profile(source)))
            self.reach(self.rules[15],**self.interior_source)

    def first_learning_settled(self,tick):
        self.check('after-first-learning',self.program.schedule,'only declared separated learning has a maturity witness')
        self.check('refill-holding',self.phase,'first learning matures under uninterrupted read competition')
        self.check(None,self.first_settled,'first effect is qualified once')
        self.check((4,4),(len(self.input_ticks),len(self.offered)),'only the first late input and its complete actual proposal exist')
        self.check(False,learning_inflight(self.pipeline.model.sources.tage),'first learning must actually finish before the second send')
        self.check(self.concrete(self.program.pending_after[0]),pending_plan(self.pipeline.model.sources.tage,self.table,self.bank),
            'complete first logical effect and unrelated pending obligation mature together')
        self.check(self.dirty_for(self.program.pending_after[0]),tuple(tuple(v) for v in self.last[1]['dirty']),
            'actual first pending state agrees before second acceptance')
        self.check((1,1),tuple(map(len,self.written.values())),'no hidden service separates the late inputs')
        self.check(True,tick>=self.offered[3]['tick'],'maturity cannot precede its actual proposal')
        self.first_settled=dict(tick=tick,accepted=self.input_ticks[3],proposal=self.offered[3]['tick'],
            pending=deepcopy(self.program.pending_after[0]))

    def late_input_cadence(self,previous,current):
        if self.program.schedule=='adjacent-acceptance':return super().late_input_cadence(previous,current)
        self.check(True,self.first_settled is not None and current>self.first_settled['tick'],
            'second original accepts after the first independently matured learning, not after a fixed delay')

    def late_proposal_cadence(self,index,tick):
        if self.program.schedule=='adjacent-acceptance':return super().late_proposal_cadence(index,tick)
        self.check(True,self.first_settled is not None and tick>self.first_settled['tick'],
            'second actual proposal follows the first qualified current version')

    def pending(self):
        late=self.phase=='refill-holding';super().pending()
        if not late:return
        first,second=self.input_ticks[3:]
        if self.program.schedule=='adjacent-acceptance':
            self.check(True,second<self.offered[3]['tick'],'second input really overlaps the first learning pipeline')
            self.check(None,self.first_settled,'overlap cannot borrow a separated maturity witness')
        else:
            self.check(True,first<self.first_settled['proposal']<=self.first_settled['tick']<second,
                'actual first acceptance, proposal, maturity and second acceptance are ordered')
        self.reach(self.rules[16],schedule=self.program.schedule,accepted=(first,second),
            proposals=tuple(row['tick'] for row in self.offered[3:]),first_settled=deepcopy(self.first_settled))

    def snapshot(self):
        return dict(super().snapshot(),interior_original=deepcopy(self.interior_source),
            first_learning_settled=deepcopy(self.first_settled),schedule=self.program.schedule)
