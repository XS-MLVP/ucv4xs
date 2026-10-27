"""Old request identity and current logical ownership are distinct obligations."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from bpuverify.bpu.coverage.direction_service import DirectionServiceCoverage

RULES=('real-key-migrates-to-other-way','original-strong-feedback-needs-no-reread',
    'proposal-keeps-old-way-and-counter','commit-uses-current-owner-and-counter',
    'new-owner-consumes-forwarded-result','neighbour-useful-and-displaced-miss-preserved')


def migration_coverage(original_way,status):
    if type(original_way) is not int or original_way not in (0,1) or status not in ('reached','checked'):
        raise ValueError('unknown direction-migration scope')
    return CoverGroupDef('bpu_owned_direction_migration_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES}),
    )).instantiate(f'kunminghu_v3.bpu.owned-direction-migration.{original_way}.{status}',
        contract='genuine old provider -> real migration -> old proposal -> current-owner commit -> all consumers')


class DirectionMigrationCoverage(DirectionServiceCoverage):
    rules=RULES
    def __init__(self,original_way):self.groups={status:migration_coverage(original_way,status) for status in ('reached','checked')}
    def write(self,output):write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-direction-migration.json')
