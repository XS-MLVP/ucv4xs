"""Direction lifecycle obligations; size is a workload, not bank enumeration."""
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.ahead_working_set import SIZES
from suites.frontend.bpu.bpu.model.ahead_correction import AheadCorrectionProgram, RULES, SELECTIONS


class AheadCorrectionCoverage:
    def __init__(self, program):
        self.program, self.evidence = program, None
        keys = tuple(f'{size}.{selection}.{rule}' for size in SIZES for selection in SELECTIONS for rule in RULES)
        self.groups = {status:CoverGroupDef('bpu_ahead_direction_working_set_v1', (
            CoverPointDef('obligation', {key:Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.ahead-direction-working-set.'+status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if rule not in RULES: raise ValueError('unknown direction working-set obligation')
        self.groups[status].sample(dict(obligation=self.program.label+'.'+rule), metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-ahead-direction-working-set.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('ahead_direction_working_set', json.dumps(self.evidence, ensure_ascii=False)))
