"""Accepted retarget event and its independently checked target consumer."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('zero-confidence-existing-region-retarget', 'zero-confidence-new-region-retarget')


def target_coverage(status):
    if status not in ('reached', 'checked'):
        raise ValueError('ITTAGE target event status must be reached or checked')
    return CoverGroupDef('ittage_full_target_learning_v1', (
        CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.ittage.full_target_learning.{status}',
        contract='accepted zero-confidence feedback -> independent committed target -> exact public metadata consumer')


class TargetLearningCoverage:
    def __init__(self):
        self.groups = {status: target_coverage(status) for status in ('reached', 'checked')}
        self.pending = {}

    def accept(self, events, model, tick):
        if events.reset:
            self.pending.clear()
            return
        feedback = events.feedback
        if (not events.enabled or feedback is None or not feedback.qualified
                or feedback.metadata.provider is None or feedback.metadata.confidence != 0
                or feedback.metadata.allocation is not None or feedback.pc >> 20 == feedback.target >> 20):
            return
        rule = RULES[0] if feedback.target >> 20 in model.regions.regions else RULES[1]
        key = feedback.pc, feedback.context, feedback.metadata.provider
        if key not in self.pending and len(self.pending) >= 64:
            raise AssertionError('ITTAGE target-obligation capacity exceeded')
        event = dict(rule=rule, pc=feedback.pc, table=feedback.metadata.provider,
                     target=feedback.target, accepted_tick=tick + 1)
        # Same-context retargets may coalesce. Superseded events retain reached
        # credit only; do not invent a checked intermediate target consumer.
        self.pending[key] = event
        self.groups['reached'].sample(dict(rule=rule), metadata=event)

    def consume(self, prediction, tick):
        if prediction is None:
            return
        for table, target in ((prediction.provider, prediction.provider_target),
                              (prediction.alternate, prediction.alternate_target)):
            key = prediction.pc, prediction.context, table
            event = self.pending.get(key)
            if event is not None and event['target'] == target:
                self.groups['checked'].sample(dict(rule=event['rule']),
                    metadata=dict(event, checked_tick=tick,
                                  role='provider' if table == prediction.provider else 'alternate'))
                del self.pending[key]

    def write(self, output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output / 'functional-coverage-full-target-learning.json')
