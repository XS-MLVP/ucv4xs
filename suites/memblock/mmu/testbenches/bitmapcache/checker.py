"""Existing refill/hit, order and byte checks (BC-01/BC-02/BC-06)."""
from suites.memblock.mmu.testbenches.bitmapcache.model import selected_byte


def check_refill_byte(resp: dict, word: int, index: int) -> None:
    expected = selected_byte(word, index)
    assert resp["hit"] == 1, index
    assert resp["order"] == index
    assert resp["cfs"] == [(expected >> bit) & 1 for bit in range(8)], (index, resp)
