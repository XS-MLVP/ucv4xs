"""Lifetime obligations, with no address or physical bank coverage axis."""
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.utage.model.working_set import MODES, RULES, SIZES


class WorkingSetCoverage:
    def __init__(self, program):
        self.program = program
        self.evidence = None
        keys = tuple(f'{size}.{mode}.{rule}' for size in SIZES for mode in MODES for rule in RULES)
        self.groups = {status: CoverGroupDef('utage_working_set_v1', (
            CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.utage.working-set.' + status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if rule not in RULES:
            raise ValueError('unknown working-set obligation')
        self.groups[status].sample(dict(obligation=f'{self.program.size}.{self.program.mode}.{rule}'),
                                   metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output / 'functional-coverage-working-set.json')

    def attach_evidence(self, properties):
        """Use pytest's retained testcase properties, not deleted worker files."""
        if self.evidence is not None:
            properties.append(('utage_working_set', json.dumps(self.evidence, ensure_ascii=False)))
