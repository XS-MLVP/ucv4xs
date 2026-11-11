"""New-baseline victim exposure and not-taken payload contracts."""
import pytest

from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.victim_training import check_payload_preservation
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.victim_training import check_victim_training


@pytest.mark.feature('BPU-MBTB-031')
@pytest.mark.parametrize('exposed', (False, True), ids=('hidden', 'exposed'))
async def test_only_the_original_exposed_victim_is_trained_in_place(mbtb_agent, exposed):
    await check_victim_training(mbtb_agent, exposed=exposed)


@pytest.mark.feature('BPU-MBTB-031')
@pytest.mark.parametrize('exposed', (False, True), ids=('hidden', 'exposed'))
async def test_second_alignment_victim_keeps_its_original_identity_and_destination(mbtb_agent, exposed):
    await check_victim_training(mbtb_agent, exposed=exposed, alignment=1)


@pytest.mark.feature('BPU-MBTB-032')
@pytest.mark.parametrize('mode', ('cold-nt', 'conditional-nt', 'false-hit'))
async def test_not_taken_feedback_preserves_target_without_disabling_false_hit_correction(mbtb_agent, mode):
    await check_payload_preservation(mbtb_agent, mode=mode)
