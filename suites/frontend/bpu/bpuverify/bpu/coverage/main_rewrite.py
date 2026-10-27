"""One complete-record version lifecycle, with independent event/effect credit."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('distinct-original-sources-own-the-same-old-branch',
    'adjacent-complete-type-and-target-corrections-with-live-predictions',
    'latest-complete-entry-replaces-pending-version-but-directions-remain-distinct',
    'fresh-consumer-still-sees-old-record-before-service',
    'only-latest-complete-entry-and-both-directions-actually-service',
    'fresh-consumer-sees-corrected-type-and-full-target',
    'clean-record-reactivates-and-services-a-new-complete-version',
    'sibling-records-and-original-snapshots-remain-unchanged')


def main_rewrite_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown complete Main record status')
    return CoverGroupDef('bpu_owned_main_rewrite_v1',(CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
        f'kunminghu_v3.bpu.owned-main-rewrite.{status}',
        contract='original branch -> full version supersession -> old visibility -> latest-only service -> clean reactivation -> fresh full consumer')


class MainRewriteCoverage:
    def __init__(self):self.groups={s:main_rewrite_coverage(s) for s in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for g in self.groups.values():g.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-main-rewrite.json')
