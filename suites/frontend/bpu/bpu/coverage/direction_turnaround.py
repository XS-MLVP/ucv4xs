"""Opposite correct-source feedback retains its current logical obligation."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.coverage.mixed_visibility import RULES as VISIBILITY_RULES
from suites.frontend.bpu.bpu.model.tage.direction_turnaround import PROGRAMS

RULES=(*VISIBILITY_RULES,'opposed-original-prediction-epochs-qualified',
       'each-late-outcome-correct-in-its-original-prefix',
       'source-boundary-does-not-replace-current-arithmetic')


class DirectionTurnaroundCoverage:
    def __init__(self,program):
        if program not in PROGRAMS:raise ValueError('unknown direction-turnaround program')
        self.groups={role:CoverGroupDef('bpu_direction_turnaround_v1',(
            CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.direction-turnaround.{program.name}.{role}') for role in ('reached','checked')}

    def record(self,role,rule,**witness):
        if role not in self.groups or rule not in RULES:raise ValueError('unknown turnaround obligation')
        self.groups[role].sample(dict(rule=rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/'functional-coverage-direction-turnaround.json')
