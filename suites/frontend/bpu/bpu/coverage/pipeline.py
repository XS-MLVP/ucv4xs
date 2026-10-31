"""Causal pipeline events, not a physical-address or cycle-count cross."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = {
    'stream': ('held-request', 'metadata-valid-only', 'redirect-replaces-held', 'restored-history-retired', 'reopen-order'),
    'repair': ('owned-micro-hit', 'middle-owner', 'younger-squashed', 'history-rewound', 'corrected-source-retired'),
}


def pipeline_coverage(family, status):
    if family not in RULES or status not in ('reached','checked'):
        raise ValueError('unknown BPU pipeline coverage family/status')
    return CoverGroupDef('bpu_owned_pipeline_'+family+'_v1', (
        CoverPointDef('rule', {rule:Bin.values(rule) for rule in RULES[family]}),
    )).instantiate(f'kunminghu_v3.bpu.owned-pipeline.{family}.{status}',
        contract='actual public events -> independently owned tokens/history -> exact current or next-cycle comparisons')


class PipelineCoverage:
    def __init__(self, family):
        self.family = family
        self.groups = {status:pipeline_coverage(family,status) for status in ('reached','checked')}
        self.pending = []

    def record(self, status, rule, tick):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def candidates(self, row, events, cycle, model, phase, previous):
        observed = row['observed']
        public, metadata = observed['prediction'], observed['metadata']
        immediate, deferred = [], []
        if self.family == 'stream':
            if phase == 'stall':
                if public['valid'] and not events.prediction_ready:
                    immediate.append('held-request')
                if metadata['valid'] and not events.metadata_ready:
                    immediate.append('metadata-valid-only')
            if phase == 'redirect' and events.redirect is not None and not events.prediction_ready and public['valid']:
                deferred.append('redirect-replaces-held')
            if phase == 'reopen':
                if metadata['valid'] and cycle.metadata is not None and cycle.metadata.history.history:
                    immediate.append('restored-history-retired')
                if public['valid'] and events.prediction_ready and previous is not None and not previous.prediction_ready:
                    immediate.append('reopen-order')
        elif phase == 'repair':
            if observed['valids'][0] and observed['choices'][0]['taken']:
                immediate.append('owned-micro-hit')
            if public['valid'] and public['repair2']:
                immediate.append('middle-owner')
                if observed['valids'][0]:
                    deferred.append('younger-squashed')
                if cycle.tokens[1] is not None and cycle.tokens[1].early.branch.taken and not cycle.decisions[1].branch.taken:
                    if model.lookup_history(events,cycle).history != model.history.history:
                        immediate.append('history-rewound')
            if metadata['valid'] and cycle.metadata is not None and cycle.metadata.middle_corrected:
                immediate.append('corrected-source-retired')
        return immediate, deferred

    def reached(self, tick, immediate, deferred):
        for rule in (*immediate,*deferred):
            self.record('reached',rule,tick)

    def checked(self, tick, immediate, deferred):
        for expected_tick, rule in self.pending:
            if expected_tick != tick:
                raise AssertionError('deferred BPU pipeline comparison lost its exact following cycle')
            self.record('checked',rule,tick)
        for rule in immediate:
            self.record('checked',rule,tick)
        self.pending = [(tick+2,rule) for rule in deferred]

    def finish(self):
        if self.pending:
            raise AssertionError('BPU pipeline event has no following-cycle comparison')
        for group in self.groups.values():
            group.assert_coverage(100.0)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output / f'functional-coverage-owned-pipeline-{self.family}.json')
