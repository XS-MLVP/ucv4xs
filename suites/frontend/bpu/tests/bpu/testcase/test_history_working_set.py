"""Real paths, shared short prerequisites and retained long-history identities."""
import pytest

from bpuverify.bpu.case.history_working_set import (check_history_working_set,check_short_path_retention,check_short_mixed_lifetime)
from bpuverify.bpu.coverage.history_working_set import HistoryWorkingSetCoverage,ShortPathRetentionCoverage,ShortMixedPathCoverage
from bpuverify.bpu.model.history_working_set import (HistoryWorkingSetProgram,PROFILES,ShortWorkingSetProgram,
    SHORT_PROFILES,ShortMixedWorkingSetProgram,SHORT_MIXED_PROFILES)

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(7920)


@pytest.mark.feature('BPU-INT-102')
@pytest.mark.parametrize('profile',tuple(PROFILES))
async def test_real_predecessor_history_working_set_retains_selectively_corrected_learning(
        bpu_agent,bpu_sc_output,request,profile):
    program = HistoryWorkingSetProgram(profile)
    coverage = HistoryWorkingSetCoverage(program)
    try:await check_history_working_set(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)


@pytest.mark.feature('BPU-INT-102')
@pytest.mark.parametrize('profile',SHORT_MIXED_PROFILES)
async def test_short_mixed_experience_survives_selective_reversal_and_restoration(bpu_agent,bpu_sc_output,request,profile):
    program=ShortMixedWorkingSetProgram(profile)
    coverage=ShortMixedPathCoverage(program)
    try:
        await check_short_mixed_lifetime(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)


@pytest.mark.feature('BPU-INT-048')
@pytest.mark.feature('BPU-INT-066')
@pytest.mark.feature('BPU-INT-102')
@pytest.mark.parametrize('profile',SHORT_PROFILES)
async def test_short_path_learning_survives_retention_and_turnover(bpu_agent,bpu_sc_output,request,profile):
    program=ShortWorkingSetProgram(profile)
    coverage=ShortPathRetentionCoverage(program)
    try:
        await check_short_path_retention(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
