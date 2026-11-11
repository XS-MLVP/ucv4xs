"""Same low PC, crossed guard/sign and taken/NT recovery outcomes."""
import pytest

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.redirect_matrix import check_redirect_matrix
from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import REDIRECT_CASES


@pytest.mark.feature('BPU-INT-114')
@pytest.mark.parametrize('case', REDIRECT_CASES, ids=lambda c: c.label)
async def test_guarded_recovery_keeps_original_history_and_fresh_consumer(bpu_agent, case):
    await check_redirect_matrix(bpu_agent, case)
