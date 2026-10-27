"""One semantic ownership exchange, not a physical coordinate matrix."""
import pytest
from bpuverify.bpu.case.dual_migration import check_dual_migration
from bpuverify.bpu.coverage.dual_migration import DualMigrationCoverage


@pytest.mark.feature('BPU-INT-089')
async def test_two_migrated_providers_keep_opposed_old_learning_through_blocked_and_clean_service(bpu_agent, bpu_sc_output):
    coverage = DualMigrationCoverage()
    try:
        await check_dual_migration(bpu_agent, coverage)
    finally:
        coverage.write(bpu_sc_output)
