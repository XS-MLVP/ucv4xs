import pytest

from suites.frontend.bpu.bpu.case.ras.redo_unwind import check_redo_unwind
from suites.frontend.bpu.bpu.coverage.ras_redo import RedoCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-080')
@pytest.mark.parametrize('calls',(8,9),ids=('repeat-last','repeat-split'))
async def test_ras_checkpoint_redoes_call_at_compression_boundary_then_retires_real_returns(bpu_agent,calls):
    coverage = RedoCoverage(calls)
    try:
        await check_redo_unwind(bpu_agent,calls=calls,coverage=coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
