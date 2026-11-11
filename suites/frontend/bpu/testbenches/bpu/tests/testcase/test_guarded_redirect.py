import pytest

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.guarded_redirect import check_guarded_redirect


@pytest.mark.feature('BPU-INT-113')
@pytest.mark.parametrize('guarded', (False, True), ids=('no-guard-control', 'real-guard'))
async def test_redirect_guard_reaches_bpu_with_explicit_history_consumer_projections(bpu_agent, guarded):
    await check_guarded_redirect(bpu_agent, guarded=guarded)
