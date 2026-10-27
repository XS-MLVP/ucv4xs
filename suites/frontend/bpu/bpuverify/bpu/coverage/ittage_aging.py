"""Reached and checked hardware obligations, never loop/phase labels."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
RULES={
    'training':('increment','decrement','correct-unconfident-suppressed','correct-update-suppressed','saturation-reset'),
    'maintenance':('read-blocked','update-blocked','sweep-completed'),
    'consumption':('cleared-useful','retained-zero-useful'),
}


def aging_coverage(family,status):
    if family not in RULES or status not in ('reached','checked'):raise ValueError('unknown ITTAGE aging event scope')
    return CoverGroupDef(f'ittage_aging_{family}_events_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES[family]}),
    )).instantiate(f'kunminghu_v3.bpu.ittage_aging.{family}.{status}',
        contract='actual source -> independent tick/clear state -> full effect and public consumer')


class AgingCoverage:
    def __init__(self):
        self.groups={(family,status):aging_coverage(family,status) for family in RULES for status in ('reached','checked')}

    def sample(self,family,status,event):
        self.groups[family,status].sample(dict(rule=event['rule']),metadata=event)

    def require(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(list(self.groups.values())), output/'functional-coverage-ittage-aging-events.json')
