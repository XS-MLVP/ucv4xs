import pytest

from bpuverify.bpu.case.ras.redo_unwind import check_redo_unwind
from bpuverify.bpu.coverage.ras_redo import RedoCoverage
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-INT-080')
@pytest.mark.parametrize('calls',(8,9),ids=('repeat-last','repeat-split'))
async def test_ras_checkpoint_redoes_call_at_compression_boundary_then_retires_real_returns(bpu_agent,calls):
    coverage = RedoCoverage(calls)
    try:
        await check_redo_unwind(bpu_agent,calls=calls,coverage=coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
