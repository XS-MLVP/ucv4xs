"""One DUT retains two branches across shared short and distinct older paths."""
import pytest

from suites.frontend.bpu.bpu.case.short_context_ownership import check_short_context_ownership
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortContextCoverage
from suites.frontend.bpu.bpu.model.short_context_ownership import ShortContextProgram, PROFILES


@pytest.mark.feature('BPU-INT-103')
@pytest.mark.parametrize('profile', PROFILES)
async def test_short_learning_shares_old_paths_but_isolates_branch_pcs(bpu_agent,bpu_sc_output,request,profile):
    program = ShortContextProgram(profile)
    coverage = ShortContextCoverage(program)
    try:
        await check_short_context_ownership(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)


from suites.frontend.bpu.bpu.case.short_context_ownership import check_short_direction_lifetime
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortDirectionCoverage
from suites.frontend.bpu.bpu.model.short_context_ownership import ShortDirectionProgram,DIRECTION_PROFILES


@pytest.mark.feature('BPU-INT-103')
@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('profile',DIRECTION_PROFILES)
async def test_short_experience_changes_direction_and_recovers_without_long_substitution(bpu_agent,bpu_sc_output,request,profile):
    program=ShortDirectionProgram(profile)
    coverage=ShortDirectionCoverage(program)
    try:
        await check_short_direction_lifetime(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)


from suites.frontend.bpu.bpu.model.short_context_ownership import ShortCrossBranchProgram,WORKING_SET_PROFILES
from suites.frontend.bpu.bpu.coverage.short_context_ownership import ShortCrossBranchCoverage
from suites.frontend.bpu.bpu.case.short_context_ownership import check_short_cross_branch_working_set

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(597)


@pytest.mark.feature('BPU-INT-103')
@pytest.mark.parametrize('profile',WORKING_SET_PROFILES)
async def test_multiple_branch_path_experiences_survive_shared_storage_pressure_and_selective_repair(bpu_agent,bpu_sc_output,request,profile):
    program=ShortCrossBranchProgram(profile)
    coverage=ShortCrossBranchCoverage(program)
    try:
        await check_short_cross_branch_working_set(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
