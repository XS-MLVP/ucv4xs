"""Production-driver overlap with autonomous Micro/Main/history expectations."""
import pytest
from suites.frontend.bpu.bpu.case.main_service import check_main_service
from suites.frontend.bpu.bpu.coverage.main_service import MainServiceCoverage


@pytest.mark.feature('BPU-INT-093')
async def test_two_original_main_targets_retain_entry_and_direction_effects_until_actual_service(bpu_agent,bpu_sc_output):
    coverage=MainServiceCoverage()
    try:await check_main_service(bpu_agent,coverage)
    finally:coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-093')
async def test_distinct_earlier_branches_reclassify_atomically_under_read_priority_and_preserve_later_indirect_siblings(bpu_agent,bpu_sc_output):
    coverage=MainServiceCoverage(reclassify=True)
    try:await check_main_service(bpu_agent,coverage,reclassify=True)
    finally:coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-MBTB-028')
async def test_real_old_cold_source_preserves_retained_main_owner_and_negative_conditional_peer(bpu_agent,bpu_sc_output):
    coverage=MainServiceCoverage(stale=True)
    try:await check_main_service(bpu_agent,coverage,stale=True)
    finally:coverage.write(bpu_sc_output)
