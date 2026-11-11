"""Legally stable ordinary-LD S4 inputs and actual ROB-head recovery effects."""
import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.tests.ldu_s4_precise_owners import LEGAL_CASES
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.ldu_s4_precise_owners import PATTERNS
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.ldu_s4_precise_owners import PreciseOrdinaryS4Program


@pytest.mark.parametrize("page,pattern",LEGAL_CASES)
@pytest.mark.parametrize("lane",range(3))
async def test_S4_precise_ROB_head_fault_structural_release_and_cancelled_same_slot_UIDs(lsq,page,pattern,lane):
    trace=PreciseOrdinaryS4Program(lsq,lane,page)
    case=dict(page=page,pattern=pattern,lane=lane)
    try:await trace.run_program(PATTERNS[pattern])
    except BaseException as exc:
        trace.write_report(case=case,passed=False,error=repr(exc))
        raise
    trace.write_report(case=case,passed=True)
