"""Byte-address transaction APIs must not expose Chisel's pruned field units."""

from types import SimpleNamespace

import pytest

from suites.frontend.bpu.ittage.agent.main import IttageAgent
from suites.frontend.bpu.models.address import decode_pruned_pc
from suites.frontend.bpu.models.address import encode_pruned_pc


@pytest.mark.feature("ENV-IF-001")
@pytest.mark.parametrize("address", [0, 2, 0x4000_0000, 0x400F_FF00])
def test_byte_address_round_trip(address):
    assert encode_pruned_pc(address) == address // 2
    assert decode_pruned_pc(encode_pruned_pc(address)) == address


@pytest.mark.feature("ENV-IF-001")
@pytest.mark.parametrize("address", [-2, 1, 0x4000_0001])
def test_pruned_encoding_rejects_unaligned_or_negative_addresses(address):
    with pytest.raises(ValueError, match="halfword-aligned byte address"):
        encode_pruned_pc(address)


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
