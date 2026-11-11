"""Native codec-error control; not additional RAS functional credit."""
import pytest

import suites.frontend.bpu.testbenches.ras.env.agent.main as ras_main
from suites.frontend.bpu.testbenches.ras.tests.scenarios.guarded_redirect import check_guarded_call

pytestmark = pytest.mark.selftest


async def test_old_guard_truncating_codec_fails_the_same_real_restore_program(ras_agent, monkeypatch):
    calls = []
    def old_codec(pc):
        calls.append(pc)
        return (pc // 2) % (1 << 49)
    monkeypatch.setattr(ras_main, 'encode_cfi_pc', old_codec)
    with pytest.raises(AssertionError, match='restored guarded call address'):
        await check_guarded_call(ras_agent, (1 << 50) + 6)
    assert calls == [(1 << 50) + 6]
