"""Declared correction scope, no scheduler, cycle or signal mechanics."""
import pytest

from bpuverify.bpu.case.ahead_correction import check_ahead_correction
from bpuverify.bpu.coverage.ahead_correction import AheadCorrectionCoverage
from bpuverify.bpu.model.ahead_correction import AheadCorrectionProgram, SELECTIONS
from bpuverify.bpu.model.ahead_working_set import SIZES


@pytest.mark.feature('BPU-INT-100')
@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('selection', SELECTIONS)
async def test_selected_branch_directions_reverse_and_recover_without_polluting_neighbors(
        bpu_agent, bpu_sc_output, request, size, selection):
    program = AheadCorrectionProgram(size, selection)
    coverage = AheadCorrectionCoverage(program)
    try: await check_ahead_correction(bpu_agent, program, coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
