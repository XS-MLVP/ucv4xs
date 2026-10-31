"""Real owned-source iteration recovery, no register-derived golden values."""
import pytest

from suites.frontend.bpu.bpu.case.loop_iteration import check_loop_iteration, check_final_loop_iteration
from suites.frontend.bpu.bpu.coverage.loop_iteration import LoopIterationCoverage, FinalIterationCoverage
from suites.frontend.bpu.bpu.model.loop_iteration import PROGRAMS


@pytest.mark.feature('BPU-INT-099')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
async def test_original_loop_iteration_survives_younger_speculation(bpu_agent, bpu_sc_output, program):
    coverage = LoopIterationCoverage(program)
    try:
        await check_loop_iteration(bpu_agent, coverage, program)
    finally:
        coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-099')
async def test_final_direction_repair_restores_its_original_iteration(bpu_agent, bpu_sc_output):
    coverage = FinalIterationCoverage()
    try:
        await check_final_loop_iteration(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
