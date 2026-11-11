"""Same legal recovery input, damaged passive consumer observation only."""
import pytest
import suites.frontend.bpu.testbenches.bpu.env.monitor.guarded_redirect as boundary
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.redirect_matrix import check_redirect_matrix
from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import REDIRECT_CASES

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('field', ('common', 'phr'))
async def test_real_guarded_redirect_rejects_wrong_consumer_address(bpu_agent, monkeypatch, field):
    case = next(c for c in REDIRECT_CASES if c.guard == 1 and c.sign == 1 and c.taken == 0 and c.history == 'nonzero')
    original = boundary.GuardedRedirectMonitor
    injected = []
    def corrupted(agent):
        monitor = original(agent)
        decode = monitor.decoder
        def wrong(sample):
            row = decode(sample)
            if row['valid']:
                row[field] ^= 1 << 48
                injected.append(field)
            return row
        monitor.decoder = wrong
        return monitor
    monkeypatch.setattr(boundary, 'GuardedRedirectMonitor', corrupted)
    with pytest.raises(AssertionError):
        await check_redirect_matrix(bpu_agent, case)
    assert injected == [field]
