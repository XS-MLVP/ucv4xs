"""051 source qualification and consumers, separate from physical coverage."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.coverage.early_positive import RULES as DISCOVERY_RULES

AGE_RULES = ('highest-provider-real-failure', 'successful-learning-not-counted-as-failure',
    'wrong-source-next-guidance-cancelled', 'exact-qualified-failure-threshold',
    'maintenance-without-ghost-learning', 'complete-common-prestate-aging',
    'both-history-providers-consumed-after-aging', 'original-sources-preserved',
    'protected-longer-table-real-failure')
RULES = DISCOVERY_RULES + AGE_RULES


class EarlyAgingCoverage:
    def __init__(self):
        definition = CoverGroupDef('bpu_owned_early_aging_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),))
        self.groups = {status: definition.instantiate(f'kunminghu_v3.bpu.owned-early-aging.{status}',
            contract='owned S1/S3 guidance -> qualified allocation failures -> real maintenance '
                     'and cancelled younger path -> all protection cells -> fresh T/NT consumers')
            for status in ('reached', 'checked')}

    def record(self, status, rule, tick):
        self.groups[status].sample(dict(rule=rule), metadata=dict(rule=rule, tick=tick))

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output / 'functional-coverage-owned-early-aging.json')
