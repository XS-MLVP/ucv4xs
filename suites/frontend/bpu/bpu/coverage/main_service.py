"""Service closure and stale-owner discrimination are orthogonal requirements."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('actual-original-target-corrections-beside-predictions','complete-entry-and-direction-effects-retained',
    'fresh-sources-see-old-targets-before-service','full-ordered-entry-and-masked-direction-service',
    'fresh-sources-see-new-targets-after-service','negative-neighbours-and-original-snapshots-preserved')
MODES=('service','retained-owner','reclassification')


def main_service_rules(mode):
    if mode not in MODES:raise ValueError('unknown Main service mode')
    return RULES if mode!='reclassification' else (*RULES[:-1],'later-indirect-siblings-and-original-snapshots-preserved')


def main_service_coverage(mode,status):
    if mode not in MODES or status not in ('reached','checked'):raise ValueError('unknown Main service mode/status')
    definition='bpu_owned_main_reclassification_v1' if mode=='reclassification' else 'bpu_owned_main_service_v1'
    return CoverGroupDef(definition,(CoverPointDef('rule',{r:Bin.values(r) for r in main_service_rules(mode)}),)).instantiate(
        f'kunminghu_v3.bpu.owned-main-{mode}.{status}',
        contract='exact source -> complete ordinary effects -> real read blocking -> old consumers -> actual service -> new consumers')


class MainServiceCoverage:
    def __init__(self,*,stale=False,reclassify=False):
        if stale and reclassify:raise ValueError('stale-owner and current-source reclassification are separate profiles')
        mode='reclassification' if reclassify else 'retained-owner' if stale else 'service'
        self.groups={s:main_service_coverage(mode,s) for s in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for g in self.groups.values():g.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-main-service.json')
