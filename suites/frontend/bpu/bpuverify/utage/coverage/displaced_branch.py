"""Whole displaced-original lifetime is credited only after monitor cleanup."""
from toffee import Bin, CoverGroupDef, CoverPointDef
from bpuverify.utage.coverage.dual_source import Coverage as VectorCoverage
from bpuverify.utage.model.displaced_branch import OBLIGATIONS


def lifetime_coverage(status):
    if status not in ('reached','checked'): raise ValueError('unknown displaced-branch status')
    return CoverGroupDef('utage_displaced_branch_v1',(CoverPointDef('obligation',{
        name: Bin.values(name) for name in OBLIGATIONS}),)).instantiate(
            'kunminghu_v3.utage.displaced-branch.'+status)


class Coverage(VectorCoverage):
    def __init__(self, program):
        self.program, self.completed, self.closed = program, set(), False
        self.groups = {s:lifetime_coverage(s) for s in ('reached','checked')}
