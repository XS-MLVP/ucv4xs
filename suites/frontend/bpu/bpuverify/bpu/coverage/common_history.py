"""Only an executed conditional prefix owns redirect history outcomes."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('nonzero-original-history-owned','conditional-only-original-context-qualified',
    'actual-original-not-taken-recovery','only-executed-prefix-restored',
    'qualified-recovered-history-endpoint-observed','original-metadata-remains-immutable')
FAMILIES=('direct-state','direct-public','conditional-state','conditional-public')


def common_history_coverage(family,status):
    if family not in FAMILIES or status not in ('reached','checked'):raise ValueError('unknown common history family/status')
    return CoverGroupDef('bpu_owned_common_history_v1',(CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
        f'kunminghu_v3.bpu.owned-common-history.{family}.{status}',
        contract='owned nonzero lookup -> exact NT source recovery -> executed prefix only -> defined history/valid public consumer')


class CommonHistoryCoverage:
    def __init__(self,*,later_conditional,public_only):
        family=f'{"conditional" if later_conditional else "direct"}-{"public" if public_only else "state"}'
        self.groups={s:common_history_coverage(family,s) for s in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for g in self.groups.values():g.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-common-history.json')
