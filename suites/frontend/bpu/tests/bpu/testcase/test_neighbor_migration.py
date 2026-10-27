"""Independent pending history must survive the migrated key's fresh/old chain."""
import pytest
from bpuverify.bpu.case.neighbor_migration import check_neighbor_migration
from bpuverify.bpu.coverage.neighbor_migration import NeighborMigrationCoverage


@pytest.mark.feature('BPU-INT-089')
async def test_pending_neighbor_learning_survives_fresh_current_and_stale_migrated_feedback(bpu_agent, bpu_sc_output):
    coverage = NeighborMigrationCoverage()
    try:
        await check_neighbor_migration(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
