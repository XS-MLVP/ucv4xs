"""Restore/pop at compression boundaries and two genuine predecessor lifetimes."""
import pytest

from bpuverify.bpu.case.ras.return_recovery import check_return_recovery
from bpuverify.bpu.coverage.ras_return_recovery import ReturnRecoveryCoverage


@pytest.mark.feature('BPU-INT-081')
@pytest.mark.parametrize('calls',(8,9),ids=('repeat-pop','group-pop'))
@pytest.mark.parametrize('storage',('speculative','retained'))
async def test_real_return_recovery_undoes_younger_pops_before_replaying_source(bpu_agent,bpu_sc_output,calls,storage):
    coverage = ReturnRecoveryCoverage(calls,storage)
    try:
        await check_return_recovery(bpu_agent,calls=calls,storage=storage,coverage=coverage)
    finally:
        coverage.write(bpu_sc_output)
