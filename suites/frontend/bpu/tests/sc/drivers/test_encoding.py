from __future__ import annotations

import pytest

from suites.frontend.bpu.sc.transaction.types import ScBaseBranch
from suites.frontend.bpu.sc.transaction.types import ScLookup
from suites.frontend.bpu.sc.transaction.types import ScHistory
from suites.frontend.bpu.sc.driver.encoding import encode_history


async def test_lookup_encoder_maps_provider_valid_and_counter(sc_agent):
    request = ScLookup(0x4000_0040, 4, 5, 0)
    assert sc_agent._encode_s0(request) == {
        "fire": 1,
        "start_pc": 0x4000_0040,
        **encode_history(ScHistory(), (3, 10)),
    }
    values = sc_agent._encode_s2(request)
    assert values["provider_counters"][0] == {
        "valid": 0,
        "bits_value": 5,
    }
    assert values["mbtb_result"][0]["bits"]["cfiPosition"] == 4


async def test_lookup_encoder_maps_mbtb_qualification(sc_agent):
    miss = sc_agent._encode_s2(ScLookup(0x4000_0040, 4, 4, mbtb_valid=0))
    direct = sc_agent._encode_s2(ScLookup(0x4000_0040, 4, 4, branch_type=2))
    assert miss["mbtb_result"][0]["valid"] == 0
    assert direct["mbtb_result"][0]["valid"] == 1
    assert direct["mbtb_result"][0]["bits"]["attribute_branchType"] == 2


async def test_lookup_encoder_preserves_vector_slots(sc_agent):
    request = ScLookup(
        0x4000_0040, 0, 0,
        branches=(ScBaseBranch(1, 4, branch_type=2), None, ScBaseBranch(4, 5)),
    )
    values = sc_agent._encode_s2(request)
    assert [entry["valid"] for entry in values["mbtb_result"]][:4] == [1, 0, 1, 0]
    assert [entry["valid"] for entry in values["provider_counters"]][:4] == [1, 0, 1, 0]
    assert values["mbtb_result"][2]["bits"]["cfiPosition"] == 4
    assert values["provider_counters"][2]["bits_value"] == 5


@pytest.mark.parametrize("branches", [
    (),
    (None,),
    (ScBaseBranch(4, 4), ScBaseBranch(4, 5)),
    (ScBaseBranch(4, 4),) * 5,
])
async def test_lookup_rejects_invalid_vectors(sc_agent, branches):
    with pytest.raises(ValueError):
        sc_agent.submit_predict_branches(0x4000_0040, branches)
