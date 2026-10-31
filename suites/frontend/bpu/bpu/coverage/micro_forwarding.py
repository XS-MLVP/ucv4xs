"""One owner and a meaningful adjacent-update/depletion lifecycle."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES = ('weak-owner-qualified','adjacent-same-owner-accepted','positive-effects-composed',
         'three-live-consumers','depleted-after-three')


def forwarding_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('unknown MicroBTB forwarding status')
    return CoverGroupDef('bpu_micro_positive_forwarding_events_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.micro-positive-forwarding.{status}',
        contract='qualified weak owned entry -> real adjacent positive feedback -> compared confidence and distinguishing public depletion')


class MicroForwardingCoverage:
    def __init__(self):
        self.groups = {status:forwarding_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,tick):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-micro-positive-forwarding.json')
