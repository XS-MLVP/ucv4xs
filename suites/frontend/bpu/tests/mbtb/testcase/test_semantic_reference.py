"""Tag-qualified learning and counter ownership need independent oracles."""
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.mbtb.case.semantic import cleanup_zero_key, coalesced_reset, unmatched_feedback
from suites.frontend.bpu.mbtb.coverage.semantic import SemanticCoverage


@pytest.mark.feature('BPU-MBTB-027')
@pytest.mark.parametrize('same_position', (False, True), ids=('other-position-control', 'same-position'))
async def test_unhit_feedback_preserves_foreign_tag_direction(mbtb_agent, same_position):
    coverage = SemanticCoverage('miss')
    try:
        await unmatched_feedback(mbtb_agent, coverage, same_position=same_position)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))


@pytest.mark.feature('BPU-MBTB-028')
@pytest.mark.parametrize('stale', (False, True), ids=('current-metadata-control', 'stale-metadata'))
async def test_coalesced_entry_reset_preserves_negative_conditional_peer(mbtb_agent, stale):
    coverage = SemanticCoverage('owner')
    try:
        await coalesced_reset(mbtb_agent, coverage, stale=stale)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))


@pytest.mark.feature('BPU-MBTB-029')
@pytest.mark.parametrize('combined_zero', (False, True), ids=('nonzero-control', 'zero-tag-and-position'))
async def test_duplicate_clear_owns_destination_not_zero_payload_key(mbtb_agent, combined_zero):
    coverage = SemanticCoverage('cleanup')
    try:
        await cleanup_zero_key(mbtb_agent, coverage, combined_zero=combined_zero)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'mbtb'))
