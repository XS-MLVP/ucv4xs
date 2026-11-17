"""FIL-02/FIL-05 checks from the existing single-request completion case."""


def check_single_response(resp: dict, vpn: int, ppn: int) -> None:
    assert resp["valid"] == 1
    assert resp["s2xlate"] == 0
    assert resp["s1_entry_tag"] == ((vpn >> 3) & ((1 << 35) - 1))
    assert resp["s1_entry_ppn"] == ppn
    assert resp["valididx"] == [1] * 8
    assert resp["ppn_low"] == list(range(8))
