"""An altered later return response must fail for an otherwise legal program."""
from dataclasses import replace
import pytest
from suites.frontend.bpu.testbenches.ras.tests.scenarios.guarded_lifetime import check_guard_lifetime

pytestmark = pytest.mark.selftest


async def test_guarded_return_lifetime_rejects_a_truncated_later_response(ras_agent, monkeypatch):
    act = ras_agent.act
    seen = []
    async def damaged(action, **kwargs):
        actual = await act(action, **kwargs)
        if action == 1:
            seen.append(actual.top)
            return replace(actual, top=actual.top % (1 << 49))
        return actual
    monkeypatch.setattr(ras_agent, 'act', damaged)
    with pytest.raises(AssertionError):
        await check_guard_lifetime(ras_agent, (1 << 50) + 6)
    assert seen == [((1 << 50) + 8) // 2]
