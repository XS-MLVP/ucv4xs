"""Two exact old reads -> adjacent accepted learning -> new checked consumers."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES=('distinct-checkpoints-same-old-read','adjacent-complete-path-feedback',
    'opposed-dual-owner-learning','negative-forwarded-to-zero',
    'positive-forwarded-to-seven','fresh-saturated-feedback-retains-both')


def forwarding_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown direction-forwarding status')
    return CoverGroupDef('bpu_owned_direction_forwarding_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-forwarding.{status}',
        contract='two checked immutable prediction owners -> adjacent real feedback -> both independent learning effects and consumers')


class DirectionForwardingCoverage:
    def __init__(self):self.groups={status:forwarding_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))

    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-forwarding.json')
