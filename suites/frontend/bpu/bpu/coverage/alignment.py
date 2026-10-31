from functools import lru_cache
from toffee import Bin, CoverGroupDef, CoverPointDef, CrossDef
from suites.frontend.bpu.bpu.model.alignment import ALL_CASES, PHASES


@lru_cache(maxsize=1)
def definition():
    return CoverGroupDef('integrated_bpu_training_alignment_all_legal_cases', (
        CoverPointDef('case', {case.label: Bin.values(case.label) for case in ALL_CASES}, weight=0),
        CoverPointDef('phase', {phase: Bin.values(phase) for phase, _, _ in PHASES}, weight=0),
    ), crosses=(CrossDef('legal_case_phase', ('case', 'phase'), max_auto_bins=7840),))


def coverage():
    return definition().instantiate('kunminghu_v3.bpu.training_alignment')
