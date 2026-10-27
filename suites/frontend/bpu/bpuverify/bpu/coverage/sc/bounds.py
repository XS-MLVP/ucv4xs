"""Qualified threshold events: reached and checked are separate measurements."""

from bpuverify.common.coverage.exports import write_functional_coverage
from collections import Counter, deque
from copy import deepcopy
from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef, CoverageDatabase
from bpuverify.bpu.model.sc.bounds import bounds_plan, threshold_events

RULES=('increase-interior','decrease-interior','enter-lower','enter-upper',
    'leave-lower','leave-upper','reject-below-from-interior','reject-above-from-interior',
    'reject-below-at-bound','reject-above-at-bound',
    'cancel-interior','cancel-at-lower','cancel-at-upper')


def bounds_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('threshold coverage status must be reached or checked')
    return CoverGroupDef('sc_threshold_vote_resolution_v2',(
        CoverPointDef('way',{str(i):Bin.values(i) for i in range(4)}),
        CoverPointDef('rule',{name:Bin.values(name) for name in RULES}),
    ),crosses=(CrossDef('way_rule',('way','rule')),)).instantiate(
        f'kunminghu_v3.bpu.sc_threshold_votes.{status}',
        contract='actual public feedback -> qualified T1 votes -> next observed register state')


class ThresholdCoverage:
    """One in-flight T1 obligation; counters and bounded witnesses, no cycle log.

    Only the checker calls reach after associating an actual public acceptance.
    The register comparison uses the existing Scoreboard, not a second oracle.
    """
    def __init__(self):
        self.reached=bounds_coverage('reached')
        self.checked=bounds_coverage('checked')
        self.pending=None
        self.counts=Counter()
        self.checked_rules=Counter()
        self.recent=deque(maxlen=16)

    def reach(self,update,*,accepted_tick,controls_tick):
        if self.pending is not None:
            raise AssertionError('unconfirmed threshold update before next obligation')
        if controls_tick!=accepted_tick+1:
            raise AssertionError('threshold update has no immediately preceding actual acceptance')
        events=threshold_events(update)
        if not events:
            return
        self.pending=dict(accepted_tick=accepted_tick,controls_tick=controls_tick,
            committed_tick=controls_tick+1,after=list(update['after']),events=events)
        for event in events:
            self.reached.sample(event,metadata={**event,**{key:self.pending[key]
                for key in ('accepted_tick','controls_tick','committed_tick')}})
        self.counts['reached']+=len(events)

    def confirm(self,tick,actual,*,check):
        if self.pending is None:
            return
        pending=self.pending
        try:
            check(pending['committed_tick'],tick,field='threshold_event_commit_association',
                accepted_tick=pending['accepted_tick'])
            check(pending['after'],actual,field='threshold_event_full_committed_vector',
                accepted_tick=pending['accepted_tick'],events=pending['events'])
        except Exception as error:
            self.fail(error)
            raise
        for event in pending['events']:
            self.checked.sample(event,metadata={**event,'accepted_tick':pending['accepted_tick'],
                'committed_tick':tick})
            self.checked_rules[event['way'],event['rule']]+=1
        self.counts['checked']+=len(pending['events'])
        self.recent.append(dict(**deepcopy(pending),status='checked',checked_tick=tick))
        self.pending=None

    def fail(self,error):
        if self.pending is not None:
            self.counts['failed']+=len(self.pending['events'])
            self.recent.append(dict(**deepcopy(self.pending),status='failed',failure=repr(error)))
            self.pending=None

    def cancel(self,tick):
        if self.pending is not None:
            self.counts['reset_cancelled']+=len(self.pending['events'])
            self.recent.append(dict(**deepcopy(self.pending),status='reset_cancelled',checked_tick=tick))
            self.pending=None

    def require_bounds(self,way,boundary):
        bounds_plan(way,boundary)
        side='below' if boundary=='lower' else 'above'
        required={'increase-interior','decrease-interior','cancel-interior',f'cancel-at-{boundary}',
            f'enter-{boundary}',f'leave-{boundary}',f'reject-{side}-from-interior',f'reject-{side}-at-bound'}
        missing=required-{rule for (lane,rule),count in self.checked_rules.items() if lane==way and count}
        if self.pending is not None or missing:
            raise AssertionError(f'incomplete checked threshold events: {sorted(missing)}, pending={self.pending}')

    def summary(self):
        return dict(counts=dict(self.counts),pending=deepcopy(self.pending),recent=list(self.recent),
            checked_rules=[dict(way=way,rule=rule,count=count)
                for (way,rule),count in sorted(self.checked_rules.items())])

    def write(self,output,way,boundary):
        write_functional_coverage(CoverageDatabase([self.reached,self.checked]), output/f'functional-coverage-sc-threshold-events-{way}-{boundary}.json')
