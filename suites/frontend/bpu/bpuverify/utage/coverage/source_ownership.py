"""Source obligations, not physical-coordinate coverage."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.utage.model.source_ownership import ASSOCIATION_MODES, ASSOCIATION_RULES, RECOVERY_RULES


class SourceOwnershipCoverage:
    def __init__(self, program):
        self.program = program
        if program.family == 'request-ownership':
            keys = tuple(f'{mode}.{rule}' for mode in ASSOCIATION_MODES for rule in ASSOCIATION_RULES)
        else:
            keys = tuple(f'{kind}.{learning}.{rule}' for kind in ('match', 'retag')
                for learning in ('stable', 'learning') for rule in
                (*RECOVERY_RULES, 'new-content-visible') if rule != 'new-content-visible' or learning == 'learning')
        self.groups = {status: CoverGroupDef('utage_'+program.family+'_v1', (
            CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
        )).instantiate(f'kunminghu_v3.utage.semantic.{program.family}.{status}') for status in ('reached','checked')}

    def record(self, status, rule, **witness):
        self.groups[status].sample(dict(obligation=self.program.mode+'.'+rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
            output / f'functional-coverage-{self.program.family}.json')
