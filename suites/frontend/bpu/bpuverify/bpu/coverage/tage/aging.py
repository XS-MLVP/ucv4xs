"""Training, maintenance and consumption are distinct causal event families."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES={
    'training':('failed-increment','failed-saturates','reset-start-demand','reset-start-correct-update','allocation-restored'),
    'maintenance':('clear-overrides-normal-useful-update','all-banks-complete'),
    'consumer':('new-provider','retained-provider'),
}


def aging_coverage(family,status):
    if family not in RULES or status not in ('reached','checked'):raise ValueError('unknown aging event scope')
    return CoverGroupDef(f'tage_useful_aging_{family}_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES[family]}),
    )).instantiate(f'kunminghu_v3.bpu.tage_useful_aging.{family}.{status}')


class AgingCoverage:
    def __init__(self):
        self.groups={(family,status):aging_coverage(family,status) for family in RULES for status in ('reached','checked')}

    def sample(self,family,status,rule,**context):
        self.groups[family,status].sample(dict(rule=rule),metadata=context)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output/'functional-coverage-tage-useful-aging-events.json')
