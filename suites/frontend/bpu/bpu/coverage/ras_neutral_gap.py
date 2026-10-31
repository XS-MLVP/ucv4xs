"""Neutral retirement reclaims lifetime credit, never committed stack data."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('real-call-sources-exhaust-capacity-with-notifications-omitted',
    'actual-neutral-source-names-distance-two-owned-checkpoint',
    'distance-two-neutral-retirement-holds-credit-and-all-committed-data',
    'actual-neutral-source-names-the-guarded-full-capacity-checkpoint',
    'registered-neutral-retirement-reclaims-credit-without-a-stack-write',
    'capacity-guard-releases-without-an-intervening-recovery',
    'new-call-identity-reuses-reclaimed-versions-without-phantom-retirement',
    'fresh-returns-consume-new-live-frames-and-original-metadata-stays-immutable')


def neutral_gap_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown neutral-gap status')
    return CoverGroupDef('bpu_ras_neutral_gap_v1',(CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
        f'kunminghu_v3.bpu.ras-neutral-gap.{status}',
        contract='omitted call notifications; real neutral distance-two hold and guarded-gap credit release; no stack writes')


class RasNeutralGapCoverage:
    def __init__(self):self.groups={s:neutral_gap_coverage(s) for s in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-ras-neutral-gap.json')
