"""Independent short/long history classes, not every physical table or bank."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

CLASSES={0:'short',2:'long'}
RULES=('correct-original-target-feedback-beside-predictions','four-context-target-effects-retained',
    'fresh-contexts-still-see-old-confidence','read-release-commits-four-complete-targets',
    'fresh-contexts-consume-committed-confidence','original-metadata-and-foreign-regions-preserved')


def service_coverage(table,status):
    if table not in CLASSES or status not in ('reached','checked'):raise ValueError('unknown indirect service class/status')
    return CoverGroupDef('bpu_owned_indirect_service_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-indirect-service.{CLASSES[table]}.{status}',
        contract='correct old targets -> full blocked context patches -> old consumers -> exact actual service -> new consumers')


class IndirectServiceCoverage:
    def __init__(self,table):self.groups={status:service_coverage(table,status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-owned-indirect-service.json')
