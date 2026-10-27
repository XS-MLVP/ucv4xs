"""Two semantic tag classes, not a physical bank/set sweep."""
import pytest
from bpuverify.bpu.case.early_direction import check_early_direction
from bpuverify.bpu.coverage.early_direction import EarlyDirectionCoverage


@pytest.mark.feature('BPU-INT-044')
@pytest.mark.parametrize('pc',(0x40000000,0x40000008),ids=('byte-tag-control','full-tag-high-bits'))
async def test_owned_conditional_ahead_path_learns_negative_short_history_provider(bpu_agent,bpu_sc_output,pc):
    coverage=EarlyDirectionCoverage('byte-tag-control' if pc==0x40000000 else 'full-tag-high-bits')
    try:await check_early_direction(bpu_agent,pc,coverage)
    finally:coverage.write(bpu_sc_output)
