"""A whole coherent handover, never a mismatching execution, earns credit."""
from toffee import Bin,CoverGroupDef,CoverPointDef
from bpuverify.utage.coverage.dual_source import Coverage as VectorCoverage
from bpuverify.utage.model.instruction_confidence import OBLIGATIONS


def lifetime_coverage(status):
    if status not in ('reached','checked'):raise ValueError('unknown instruction-confidence status')
    return CoverGroupDef('utage_instruction_confidence_v1',(CoverPointDef('obligation',{
        name:Bin.values(name) for name in OBLIGATIONS}),)).instantiate(
            'kunminghu_v3.utage.instruction-confidence.'+status)


class Coverage(VectorCoverage):
    def __init__(self,program):
        self.program,self.completed,self.closed=program,set(),False
        self.groups={s:lifetime_coverage(s) for s in ('reached','checked')}
