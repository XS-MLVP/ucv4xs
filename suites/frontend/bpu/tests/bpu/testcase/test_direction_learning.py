"""Strengthen existing FTQ-learning requirement with an autonomous TAGE oracle."""
import pytest

from bpuverify.bpu.case.direction_learning import check_direction_learning
from bpuverify.bpu.coverage.direction_learning import DirectionCoverage


@pytest.mark.feature('BPU-INT-004')
async def test_owned_history_main_and_tage_drive_raw_and_alternate_repairs(bpu_agent,bpu_sc_output):
    coverage = DirectionCoverage()
    try:await check_direction_learning(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)
