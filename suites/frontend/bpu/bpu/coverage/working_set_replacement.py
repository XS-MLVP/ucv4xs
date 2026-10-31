"""Human semantic obligations; original physical and feature denominators stay."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from suites.frontend.bpu.bpu.model.working_set_replacement import KINDS, Program


def lifetime_coverage(status):
    keys = tuple(candidate.label + '.' + rule for kind in KINDS
                 for candidate in (Program(kind),) for rule in candidate.rules)
    definition = CoverGroupDef('bpu_ahead_identity_replacement_v1', (
        CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),))
    return definition.instantiate('kunminghu_v3.bpu.ahead-identity-replacement.' + status)


class Coverage:
    def __init__(self, program):
        self.program, self.evidence = program, None
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in self.program.rules:
            raise ValueError('unknown branch-identity lifetime obligation')
        self.groups[status].sample(dict(obligation=self.program.label + '.' + rule), metadata=witness)
