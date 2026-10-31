"""History-event reachability and independently compared response consumers."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('zero-history', 'path-feature', 'global-feature', 'backward-feature',
         'loop-feature', 'invalid-common-history', 'adjacent-distinct-contexts')


def semantic_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('SC semantic event status must be reached or checked')
    return CoverGroupDef('sc_history_semantics_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.sc.history_semantics.{status}',
        contract='accepted public history context -> owned weight snapshot -> exact public decision and metadata')


class ScHistoryCoverage:
    def __init__(self):
        self.groups = {status: semantic_coverage(status) for status in ('reached', 'checked')}
        self.pending = {}
        self.previous = None

    def accept(self, events, tick):
        if events.reset:
            self.pending.clear()
            self.previous = None
            return
        if not events.enabled or not events.ready or events.pc is None:
            return
        context = events.context
        rules = []
        if not any((context.path, context.global_history, context.backward, context.loop)):
            rules.append('zero-history')
        if context.path:
            rules.append('path-feature')
        if context.common_valid and context.global_history:
            rules.append('global-feature')
        if context.common_valid and context.backward:
            rules.append('backward-feature')
        if context.loop:
            rules.append('loop-feature')
        if not context.common_valid:
            rules.append('invalid-common-history')
        if self.previous is not None:
            previous_tick, previous_context = self.previous
            if tick == previous_tick + 2 and context != previous_context:
                rules.append('adjacent-distinct-contexts')
        self.previous = tick, context
        key = events.pc, context
        if len(self.pending) >= 64 and key not in self.pending:
            raise AssertionError('SC history-obligation capacity exceeded')
        witnesses = tuple(dict(rule=rule, pc=events.pc, context=repr(context), accepted_tick=tick + 1)
                          for rule in rules)
        self.pending[key] = witnesses
        for witness in witnesses:
            self.groups['reached'].sample(dict(rule=witness['rule']), metadata=witness)

    def consume(self, prediction, tick):
        if prediction is None:
            return
        for witness in self.pending.pop((prediction.read.pc, prediction.read.context), ()):
            self.groups['checked'].sample(dict(rule=witness['rule']),
                metadata=dict(witness, checked_tick=tick, sums=prediction.sums))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output / 'functional-coverage-history-semantics.json')
