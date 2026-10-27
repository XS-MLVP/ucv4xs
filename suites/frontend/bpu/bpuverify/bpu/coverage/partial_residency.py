"""Residency reachability is distinct from complete input/service/consumer checks."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.tage.partial_residency import PROGRAMS

RULES = ('genuine-old-sources-and-partial-residency-qualified',
         'actual-feedback-keeps-original-qualification',
         'actual-proposals-and-hit-ownership-compared',
         'latest-pending-identity-and-replacement-obligation-compared',
         'blocked-consumers-retain-old-storage',
         'only-latest-complete-owner-results-actually-service',
         'fresh-consumers-separate-resident-and-evicted-keys',
         'original-snapshots-and-unaffected-neighbors-preserved')


class PartialResidencyCoverage:
    def __init__(self, program):
        if program not in PROGRAMS:
            raise ValueError('unknown partial-residency program')
        self.groups = {status: CoverGroupDef('bpu_partial_residency_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.partial-residency.{program.name}.{status}',
                contract='genuine old source -> actual identity hit or miss -> exact pending/service -> all consumers')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(rule=rule), metadata=dict(witness=witness))

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-partial-residency.json')
