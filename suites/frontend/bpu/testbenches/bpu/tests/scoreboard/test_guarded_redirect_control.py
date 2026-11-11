"""Native input corruption control; not RTL mutation or hardware credit."""
import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.guarded_redirect import check_guarded_redirect

pytestmark = pytest.mark.selftest


async def test_real_truncated_guard_does_not_redefine_the_planned_redirect(bpu_agent, monkeypatch):
    send = bpu_agent.redirect_driver.send
    injected = []
    async def wrong(payload):
        injected.append(payload['cfi_pc'])
        await send({**payload, 'cfi_pc': payload['cfi_pc'] % (1 << 49)})
    monkeypatch.setattr(bpu_agent.redirect_driver, 'send', wrong)
    with pytest.raises(ScoreboardMismatch):
        await check_guarded_redirect(bpu_agent, guarded=True)
    assert injected == [0x40000804 + (1 << 49)]
