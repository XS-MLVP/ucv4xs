"""Confidence trajectories are functional obligations, not bank enumerations."""
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase
from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.coverage.direction_turnaround import RULES as ORIGINAL_RULES
from suites.frontend.bpu.bpu.model.tage.confidence_boundary import PROGRAMS

RULES=(*ORIGINAL_RULES,'every-delayed-outcome-has-a-distinct-real-prediction',
       'every-current-confidence-step-and-final-boundary-compared',
       'all-auxiliary-main-direction-updates-accepted-without-loss',
       'each-training-history-still-reconstructs-its-original-prediction')


class ConfidenceBoundaryCoverage:
    def __init__(self,program,*,traffic='returning'):
        if program not in PROGRAMS:raise ValueError('unknown confidence-boundary program')
        if traffic not in ('returning','fallthrough'):raise ValueError('unknown read traffic semantics')
        suffix='' if traffic=='returning' else 'stable-history.'
        self.groups={role:CoverGroupDef('bpu_confidence_boundary_v1',(
            CoverPointDef('rule',{r:Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.confidence-boundary.{suffix}{program.name}.{role}') for role in ('reached','checked')}

    def record(self,role,rule,**witness):
        if role not in self.groups or rule not in RULES:raise ValueError('unknown confidence-boundary obligation')
        self.groups[role].sample(dict(rule=rule),metadata=witness)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),
                                  output/'functional-coverage-confidence-boundary.json')
