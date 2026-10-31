"""Independent ahead prediction and source-qualified S3 replay."""
import pytest
from suites.frontend.bpu.bpu.case.ahead_learning import check_ahead_learning
from suites.frontend.bpu.bpu.coverage.ahead_learning import AheadLearningCoverage


@pytest.mark.feature('BPU-INT-015')
@pytest.mark.feature('BPU-INT-019')
async def test_owned_ahead_reads_learn_both_loop_edges_and_replay_after_target_correction(bpu_agent,bpu_sc_output):
    coverage=AheadLearningCoverage()
    try:await check_ahead_learning(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
