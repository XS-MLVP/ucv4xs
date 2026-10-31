"""066 opposed-base qualification, not new physical-address feature points."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.bpu.coverage.early_direction import RULES as LEARNING_RULES

EXTRA_RULES=('strong-negative-provider','same-ahead-owner-distinct-provider-history',
    'main-negative-with-positive-base-held','opposed-provider-selects-later-jump',
    'correct-opposed-provider-useful-increase','original-opposed-sources-immutable')
RULES=LEARNING_RULES+EXTRA_RULES


def opposition_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown opposed early direction status')
    return CoverGroupDef('bpu_owned_early_opposition_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-early-opposition.{status}',
        contract='real independent source learning -> same Ahead owner / other history -> opposed S1 choice -> source-qualified useful increase')


class EarlyOppositionCoverage:
    def __init__(self):self.groups={status:opposition_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-early-opposition.json')
