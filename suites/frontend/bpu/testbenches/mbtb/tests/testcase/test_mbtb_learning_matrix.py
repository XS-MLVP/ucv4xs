"""Type/outcome/address and original-exposure/current-residency matrices."""
import pytest

from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.learning_matrix import check_payload_matrix
from suites.frontend.bpu.testbenches.mbtb.tests.scenarios.learning_matrix import check_residency_matrix
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import RESIDENCY_CASES


@pytest.mark.feature('BPU-MBTB-033')
@pytest.mark.parametrize('case', PAYLOAD_CASES, ids=lambda c: c.label)
async def test_resolved_not_taken_preserves_owned_payload_and_neighbor(mbtb_agent, case):
    await check_payload_matrix(mbtb_agent, case)


@pytest.mark.feature('BPU-MBTB-034')
@pytest.mark.parametrize('case', RESIDENCY_CASES, ids=lambda c: c.label)
async def test_delayed_original_victim_feedback_rechecks_current_residency(mbtb_agent, case):
    await check_residency_matrix(mbtb_agent, case)
