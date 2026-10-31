"""PHR scenarios express intent; drivers, observation and matching stay in the library."""

import pytest

from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.bpu.case.phr_recovery import check_recovery
from suites.frontend.bpu.bpu.case.phr_direction_repair import check_override
from suites.frontend.bpu.bpu.case.phr_taken_wrap import check_taken_wrap


@pytest.mark.feature('BPU-INT-034')
@pytest.mark.parametrize('mode', ('flowing', 'backpressured'))
async def test_phr_external_recovery_uses_captured_metadata(bpu_agent, mode):
    await check_recovery(bpu_agent, REPO_ROOT, mode=mode)


@pytest.mark.parametrize('stage', (
    pytest.param('s2', marks=pytest.mark.feature('BPU-INT-035')),
    pytest.param('s3', marks=pytest.mark.feature('BPU-INT-036')),
))
@pytest.mark.parametrize('mode', ('flowing', 'backpressured'))
async def test_phr_not_taken_direction_repair(bpu_agent, stage, mode):
    await check_override(bpu_agent, REPO_ROOT, stage=stage, mode=mode)


@pytest.mark.parametrize('stage', (
    pytest.param('s2', marks=pytest.mark.feature('BPU-INT-037')),
    pytest.param('s3', marks=pytest.mark.feature('BPU-INT-038')),
))
@pytest.mark.parametrize('mode', ('flowing', 'backpressured'))
async def test_phr_taken_repair_wraps_pointer_zero(bpu_agent, stage, mode):
    await check_taken_wrap(bpu_agent, REPO_ROOT, stage=stage, mode=mode)
