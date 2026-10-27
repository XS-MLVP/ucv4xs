"""Intent-only checks for accepted adjacent masks and dirty/clean lifecycles."""
import pytest

from bpuverify.bpu.case.sc.scenarios import cases
from bpuverify.bpu.case.sc.supplemental import check_masked_feedback
from bpuverify.bpu.coverage.sc.supplemental import matrix_coverage

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(20)

def identity(case):
    return (f"bank{case['bank']}-row{case['row']}-pair{case['positions'][0]}_{case['positions'][1]}-"
            f"{case['order']}-{case['lifecycle']}")


@pytest.mark.feature('BPU-INT-039')
@pytest.mark.parametrize('case', [case for case in cases() if case['lifecycle'] == 'dirty_merge'], ids=identity)
async def test_adjacent_distinct_mask_sc_feedback_preserves_pending_lanes(bpu_agent, bpu_sc_output, case):
    await check_masked_feedback(bpu_agent, bpu_sc_output, case, matrix_coverage())


@pytest.mark.feature('BPU-INT-040')
@pytest.mark.parametrize('case', [case for case in cases() if case['lifecycle'] == 'clean_reactivate'], ids=identity)
async def test_drained_sc_masked_entry_reactivates_without_losing_other_lanes(bpu_agent, bpu_sc_output, case):
    await check_masked_feedback(bpu_agent, bpu_sc_output, case, matrix_coverage())
