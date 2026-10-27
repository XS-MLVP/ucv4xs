"""062: autonomous full-history indirect learning, final repair and retarget."""
import pytest
from bpuverify.bpu.case.indirect_learning import check_indirect_learning
from bpuverify.bpu.coverage.indirect_learning import IndirectLearningCoverage


@pytest.mark.feature('BPU-INT-062')
async def test_owned_indirect_target_repairs_main_until_original_zero_confidence_learning_completes(bpu_agent,bpu_sc_output):
    coverage=IndirectLearningCoverage()
    try:await check_indirect_learning(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
