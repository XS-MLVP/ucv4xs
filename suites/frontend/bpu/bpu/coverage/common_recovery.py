"""Real source, actual recovery, committed state and fresh consumer are paired."""
from copy import deepcopy

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.common_recovery import PROFILES

RULES = ('original-pattern-and-conditional-identities-owned',
         'immutable-original-prediction-qualified',
         'actual-complete-original-recovery-accepted',
         'only-executed-conditional-prefix-restored',
         'fresh-valid-public-consumer-compared',
         'complete-original-metadata-remains-immutable')


class CommonRecoveryCoverage:
    def __init__(self, profile):
        if profile not in PROFILES:
            raise ValueError('unknown semantic recovery profile')
        self.witnesses = {}
        self.groups = {status: CoverGroupDef('bpu_common_recovery_v1', (
            CoverPointDef('rule', {rule: Bin.values(rule) for rule in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.common-recovery.{profile.name}.{status}',
                contract='owned source -> actual recovery -> executed prefix -> committed state and fresh public consumer')
            for status in ('reached', 'checked')}

    def record(self, status, rule, tick, *, witness=None):
        if witness is not None:
            self.witnesses[rule] = deepcopy(witness)
        metadata = dict(tick=tick)
        if rule in self.witnesses:
            metadata['witness'] = deepcopy(self.witnesses[rule])
        self.groups[status].sample(dict(rule=rule), metadata=metadata)

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-common-recovery.json')
