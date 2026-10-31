"""Actual pending-operation events, separate reached and checked effects."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from collections import Counter, deque
from copy import deepcopy
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from suites.frontend.bpu.bpu.model.ras.micro_events import pending_interaction

RULES=('return-pairs-S2-forwards-S3','return-pairs-S3-uses-main',
    'neutral-S2-cancel-S1-CALL','neutral-S2-cancel-S1-RETURN')


def micro_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('MicroRAS event status must be reached or checked')
    return CoverGroupDef('micro_ras_pending_interactions_v2',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.micro_ras_events.{status}',
        contract='qualified pending interaction -> next full MicroRAS state and output comparison')


class MicroRasEvents:
    """Coverage bookkeeping only; the existing Scoreboard compares all state."""
    def __init__(self):
        self.reached=micro_coverage('reached')
        self.checked=micro_coverage('checked')
        self.pending=None
        self.counts=Counter()
        self.recent=deque(maxlen=64)

    def reach(self,state,inputs,*,tick,reset):
        if self.pending is not None:
            raise AssertionError('MicroRAS interaction has no checked next state')
        event=pending_interaction(state,inputs,reset)
        if event is not None:
            self.pending=dict(**event,tick=tick,committed_tick=tick+2)
            self.reached.sample(event,metadata=self.pending)
            self.counts['reached']+=1

    def confirm(self,tick,*,check):
        if self.pending is not None:
            check(self.pending['committed_tick'],tick,'MicroRAS interaction commit association',
                event=self.pending)
            self.checked.sample(self.pending,metadata=dict(self.pending,checked_tick=tick))
            self.recent.append(dict(self.pending,status='checked'))
            self.counts['checked']+=1
            self.pending=None

    def fail(self,error):
        if self.pending is not None:
            self.recent.append(dict(self.pending,status='failed',failure=repr(error)))
            self.counts['failed']+=1
            self.pending=None

    def require(self,rule,tick,*,check):
        matches=[row for row in self.recent if row['rule']==rule and row['tick']==tick and row['status']=='checked']
        check(1,len(matches),'exact associated checked MicroRAS interaction',rule=rule,tick=tick)

    def summary(self):
        return dict(counts=dict(self.counts),pending=deepcopy(self.pending),recent=list(self.recent))

    def write(self,output,label):
        write_functional_coverage(CoverageDatabase([self.reached,self.checked]), output/f'functional-coverage-micro-ras-events-{label}.json')
