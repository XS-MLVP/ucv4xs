"""VTypeGen independent-oracle audit."""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType
from suites.frontend.ibuffer.testbenches.vtype_gen.model import StimulusError
from suites.frontend.ibuffer.testbenches.vtype_gen.model import decode_vtype
from suites.frontend.ibuffer.testbenches.vtype_gen.model import encode_vsetvli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import lane_window


def vset(vsew: int, vlmul: int, rd: int = 5, rs1: int = 10) -> int:
    return encode_vsetvli(rd, rs1, ((vsew & 7) << 3) | (vlmul & 7))


@pytest.mark.feature("IBUF-ENV-004")
def test_vtype_oracle_rejects_every_reserved_encoding():
    for vsew in range(8):
        for vlmul in range(8):
            supported, vlmax = decode_vtype(vsew, vlmul)
            if vlmul == 4:
                assert not supported and vlmax == 0
            if vsew >= 4:
                assert not supported and vlmax == 0
    # ELEN=64 upper bound for fractional LMUL.
    assert decode_vtype(3, 7) == (False, 0)      # e64 mf2: 64 > 32
    assert decode_vtype(2, 7) == (True, 2)       # e32 mf2: 32 == 32
    assert decode_vtype(0, 5) == (True, 2)       # e8 mf8: 8 == 8
    assert decode_vtype(1, 5) == (False, 0)      # e16 mf8: 16 > 8


@pytest.mark.feature("IBUF-ENV-004")
def test_lane_chain_keep_vl_rule_uses_the_window_not_the_register():
    spec = VType(0, 0, 0, 0, 0)                   # e8 m1, VLMAX=16
    # Lane 0 changes VLMAX to 4; lane 1 keeps vl at the same VLMAX, which is
    # legal only because the chain (not the register) is the reference.
    lanes = ((1, vset(2, 0)), (1, vset(1, 7, rd=0, rs1=0))) + ((0, 0),) * 6
    vtype, _ = lane_window(lanes, spec)
    assert vtype[0] == VType(0, 0, 0, 2, 0)
    assert vtype[1] == VType(0, 0, 0, 1, 7)
    # A change against the updated reference is reserved and reports vill.
    lanes = ((1, vset(2, 0)), (1, vset(3, 0, rd=0, rs1=0))) + ((0, 0),) * 6
    vtype, _ = lane_window(lanes, spec)
    assert vtype[0] == VType(0, 0, 0, 2, 0)
    assert vtype[1].illegal == 1


@pytest.mark.feature("IBUF-ENV-004")
def test_vtype_validation_rejects_out_of_range_fields():
    with pytest.raises(StimulusError):
        VType(vsew=8)
    with pytest.raises(StimulusError):
        VType(vlmul=8)
    with pytest.raises(StimulusError):
        VType(illegal=2)
