"""Acceptance, deferred visibility and committed consumers are distinct events."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

RULES=('nonreread-accepted-under-read','prediction-feedback-concurrent',
    'four-history-owner-results-retained','both-histories-still-see-old-entries',
    'release-retires-each-history-owner-once','both-histories-consume-all-commits')


def service_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown direction-service status')
    return CoverGroupDef('bpu_owned_direction_service_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-service.{status}',
        contract='actual concurrent feedback/read -> exact blocked pending writes -> old consumer -> SDK write acceptance -> new consumer')


class DirectionServiceCoverage:
    rules=RULES
    def __init__(self):self.groups={status:service_coverage(status) for status in ('reached','checked')}
    def record(self,status,rule,tick):self.groups[status].sample(dict(rule=rule),metadata=dict(tick=tick))
    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-service.json')
