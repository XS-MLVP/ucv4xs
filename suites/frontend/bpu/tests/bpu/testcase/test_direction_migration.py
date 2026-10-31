"""Two cross-owner directions, not a bank/depth Cartesian product."""
import pytest
from suites.frontend.bpu.bpu.case.direction_migration import check_direction_migration
from suites.frontend.bpu.bpu.coverage.direction_migration import DirectionMigrationCoverage


@pytest.mark.feature('BPU-INT-089')
@pytest.mark.parametrize('original_way',(0,1),ids=('old-way0','old-way1'))
async def test_original_strong_feedback_commits_to_current_migrated_owner_and_preserves_neighbours(bpu_agent,bpu_sc_output,original_way):
    coverage=DirectionMigrationCoverage(original_way)
    try:await check_direction_migration(bpu_agent,coverage,original_way)
    finally:coverage.write(bpu_sc_output)
