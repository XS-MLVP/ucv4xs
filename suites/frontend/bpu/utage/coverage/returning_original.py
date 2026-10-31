"""A complete original-contribution and identity-rebuild cohort is one proof."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from suites.frontend.bpu.utage.coverage.read_lifetime import LateReplacementCoverage
from suites.frontend.bpu.utage.model.returning_original import PROGRAMS, RULES


def lifetime_coverage(status):
    if status not in ('reached', 'checked'): raise ValueError('unknown original-return status')
    definition = CoverGroupDef('utage_returning_original_v1', (CoverPointDef('obligation', {
        program.label+'.'+rule: Bin.values(program.label+'.'+rule)
        for program in PROGRAMS for rule in RULES}),))
    return definition.instantiate('kunminghu_v3.utage.returning-original.'+status)


class Coverage(LateReplacementCoverage):
    def __init__(self, program):
        self.program, self.completed, self.closed = program, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}
