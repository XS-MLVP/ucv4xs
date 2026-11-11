"""Byte-address transaction APIs must not expose Chisel's pruned field units."""

import pytest

from suites.frontend.bpu.testbenches.ubtb.model.address import decode_pruned_pc
from suites.frontend.bpu.testbenches.ubtb.model.address import encode_pruned_pc


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
