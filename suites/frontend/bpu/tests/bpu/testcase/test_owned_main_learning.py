"""Strengthen the existing FTQ-learning requirement with an independent oracle."""
import pytest

from bpuverify.bpu.case.main_learning import check_owned_main_learning
from bpuverify.bpu.coverage.main_learning import MainLearningCoverage


@pytest.mark.feature('BPU-INT-004')
@pytest.mark.parametrize('pc',(0x40000800,0x4000080b),ids=('aligned-window','rotated-unaligned-window'))
async def test_ftq_learning_and_direction_recovery_keep_their_exact_owned_source(bpu_agent,bpu_sc_output,pc):
    coverage = MainLearningCoverage()
    try:
        await check_owned_main_learning(bpu_agent,coverage,pc=pc)
    finally:
        coverage.write(bpu_sc_output)
