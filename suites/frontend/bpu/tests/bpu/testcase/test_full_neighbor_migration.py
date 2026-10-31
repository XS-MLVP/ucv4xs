"""Full retained capacity must not turn a migrated-key hit into replacement."""
import pytest
from suites.frontend.bpu.bpu.case.full_neighbor_migration import check_full_neighbor_migration
from suites.frontend.bpu.bpu.coverage.full_neighbor_migration import FullNeighborMigrationCoverage


@pytest.mark.feature('BPU-INT-089')
async def test_full_pending_capacity_preserves_three_neighbors_during_stale_migrated_key_hits(bpu_agent, bpu_sc_output):
    coverage = FullNeighborMigrationCoverage()
    try:
        await check_full_neighbor_migration(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
