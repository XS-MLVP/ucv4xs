"""066 opposite-polarity qualification includes, but does not replace, NT proof."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.coverage.early_opposition import RULES as NEGATIVE_RULES

EXTRA_RULES=('positive-seed-original-source-learning','positive-seed-protected-by-negative-base-history',
    'main-positive-with-negative-base-held','positive-provider-selects-earlier-conditional',
    'positive-original-source-useful-increase','both-polarities-original-sources-immutable')
RULES=NEGATIVE_RULES+EXTRA_RULES


def positive_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown positive early opposition status')
    return CoverGroupDef('bpu_owned_early_positive_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-early-positive.{status}',
        contract='original-source positive learning -> NT base preserves key -> T source selects earlier branch -> actual useful confirmation')


class EarlyPositiveCoverage:
    def __init__(self):self.groups={status:positive_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-early-positive.json')
