"""Upper hash collisions must obey useful qualification and tag identity."""

import pytest

from bpuverify.utage.coverage.catalog import utage_history_collision_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_history_collision_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.collision_scenario import check_history_collisions


@pytest.mark.feature("BPU-UTAGE-019")
async def test_upper_hash_collisions_reallocate_tags_and_replay_captured_counters(utage_agent):
    coverage = utage_history_collision_coverage_model()
    await check_history_collisions(utage_agent, coverage)
    coverage.assert_coverage(100.0)
    write_utage_history_collision_coverage(coverage, REPO_ROOT)
