"""Valid unmatched branches must not shift, acquire or corrupt learning owners."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase


RULES = ('interleaved-valid-feedback','position-qualified-owners','correct-opposed-learning',
         'all-owned-results-consumed','untracked-feedback-filtered','no-accidental-provider-on-discovery')


def interleaved_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown interleaved learning status')
    return CoverGroupDef('bpu_tage_interleaved_resolve_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.tage.interleaved-resolve.{status}',
        contract='accepted tracked/untracked valid branches -> position-owned learning -> all consumers and later untracked discovery')


class InterleavedCoverage:
    def __init__(self):
        self.groups = {status:interleaved_coverage(status) for status in ('reached','checked')}

    def record(self,status,rule,**witness):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,**witness))

    def finish(self):
        for group in self.groups.values():group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-tage-interleaved.json')
