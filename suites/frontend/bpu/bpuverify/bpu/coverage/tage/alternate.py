"""Provider promotion, alternate selection and their real pipeline consumers."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = ('promoted-provider-keeps-alternate','alternate-over-opposing-base','raw-middle-redirect',
         'alternate-final-redirect','strong-provider-reclaims','sentinel-unmodified')


def alternate_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('unknown TAGE alternate event status')
    return CoverGroupDef('bpu_tage_alternate_hierarchy_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.tage.alternate-hierarchy.{status}',
        contract='actual promoted provider/alternate event -> independent table state -> complete associated S2/S3 consumer')


class AlternateCoverage:
    def __init__(self):
        self.groups = {status:alternate_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,**witness))

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-tage-alternate.json')
