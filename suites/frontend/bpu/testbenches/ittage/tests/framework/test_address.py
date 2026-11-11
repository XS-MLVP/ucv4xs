"""Byte-address transaction APIs must not expose Chisel's pruned field units."""

from types import SimpleNamespace

import pytest

from suites.frontend.bpu.testbenches.ittage.env.agent.main import IttageAgent


@pytest.mark.feature("ENV-IF-001")
def test_ittage_monitor_decodes_both_target_metadata_fields():
    value = lambda number: SimpleNamespace(as_int=lambda: number)
    prediction = IttageAgent._decode(SimpleNamespace(
        hit=value(1), target=value(0x2008_0090),
        meta={
            "providerTarget_addr": value(0x2008_0090),
            "altProviderTarget_addr": value(0x2000_0090),
        },
    ))
    assert prediction.target == 0x4010_0120
    assert prediction.meta["providerTarget_addr"] == 0x4010_0120
    assert prediction.meta["altProviderTarget_addr"] == 0x4000_0120
