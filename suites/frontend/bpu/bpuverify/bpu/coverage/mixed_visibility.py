"""Per-identity visibility and service obligations, not slot combinations."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.tage.mixed_visibility import PROGRAMS

RULES = ('two-original-providers-migrate-together',
         'normal-target-and-neighbor-preparation-qualified',
         'new-feedback-keeps-original-or-mixed-visibility-source',
         'each-remaining-pending-result-and-reactivation-compared',
         'mixed-storage-remains-visible-while-new-learning-waits',
         'all-independent-identity-services-compared',
         'all-final-history-consumers-compared',
         'original-snapshots-and-unresolved-neighbors-preserved',
         'asymmetric-prelude-proposals-qualified',
         'only-first-different-history-results-actually-serviced',
         'mixed-consumers-own-independent-storage-versions',
         'initial-consumers-precede-any-service')


class MixedVisibilityCoverage:
    def __init__(self, program):
        if program not in PROGRAMS:
            raise ValueError('unknown mixed-visibility program')
        self.groups = {role: CoverGroupDef('bpu_mixed_visibility_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.mixed-visibility.{program.name}.{role}') for role in ('reached', 'checked')}

    def record(self, role, rule, **witness):
        if role not in self.groups or rule not in RULES:
            raise ValueError('unknown mixed-visibility evidence role or requirement')
        self.groups[role].sample(dict(rule=rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-mixed-visibility.json')
