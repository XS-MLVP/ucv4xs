"""Exhaustive legal input intent; no raw pins, edges or event-loop scheduling."""
import pytest
from suites.frontend.bpu.bpu.model.alignment import ALL_CASES
from suites.frontend.bpu.bpu.case.alignment import check_training_alignment

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(25)


@pytest.mark.feature('BPU-INT-059')
@pytest.mark.parametrize('case', ALL_CASES, ids=[case.label for case in ALL_CASES])
async def test_real_feedback_all_legal_alignments_and_positions(bpu_agent, bpu_sc_output, case):
    await check_training_alignment(bpu_agent, bpu_sc_output, case)
