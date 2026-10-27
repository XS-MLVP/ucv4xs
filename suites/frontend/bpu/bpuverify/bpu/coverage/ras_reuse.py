"""Owned capacity recovery and version reuse; physical positions are not bins."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('real-call-sources-fill-the-bounded-speculative-capacity',
    'additional-call-offers-are-guarded-without-new-versions',
    'guarded-returns-and-current-source-restore-preserve-the-prefix',
    'genuine-older-source-restores-below-the-guard-boundary',
    'recovered-old-returns-and-surviving-original-calls-retire',
    'different-address-call-versions-reuse-cancelled-and-reclaimed-storage',
    'younger-new-call-is-cancelled-and-kept-new-calls-retire-once',
    'fresh-new-returns-and-retained-old-frames-remain-correct')


def ras_reuse_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown RAS reuse status')
    return CoverGroupDef('bpu_ras_reclaimed_versions_v1',(CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
        f'kunminghu_v3.bpu.ras-reclaimed-versions.{status}',
        contract='actual full/guard -> exact older rollback -> owned retirement -> new-address wrap/reuse -> fresh return')


class RasReuseCoverage:
    def __init__(self):self.groups={s:ras_reuse_coverage(s) for s in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for g in self.groups.values():g.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-ras-reclaimed-versions.json')
