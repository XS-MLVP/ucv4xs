"""Independent byte-lane and corrupt completion controls for BC-01/BC-02/BC-06."""
import pytest

from suites.memblock.mmu.testbenches.bitmapcache.checker import check_refill_byte
from suites.memblock.mmu.testbenches.bitmapcache.model import selected_byte

pytestmark = pytest.mark.selftest


def test_refill_hit_rejects_wrong_lane_order_or_hit():
    word = 0x0102030405060708
    assert [selected_byte(word, index) for index in range(8)] == [8, 7, 6, 5, 4, 3, 2, 1]
    clean = dict(hit=1, order=0, cfs=[0, 0, 0, 1, 0, 0, 0, 0])
    for field, bad in (("hit", 0), ("order", 1), ("cfs", [0] * 8)):
        check_refill_byte(clean, word, 0)
        with pytest.raises(AssertionError):
            check_refill_byte(clean | {field: bad}, word, 0)
