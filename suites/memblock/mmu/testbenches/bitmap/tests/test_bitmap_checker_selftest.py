"""Independent examples and corrupt completion controls for BM-01/BM-03/BM-04."""
import pytest

from suites.memblock.mmu.testbenches.bitmap.checker import check_response
from suites.memblock.mmu.testbenches.bitmap.model import merge_ppn

pytestmark = pytest.mark.selftest


def test_bitmap_completion_rejects_wrong_result_or_id():
    assert merge_ppn(0x80000, 0x12345, 0x1FF) == 0x80145
    assert merge_ppn(0x80000, 0x12345, 0x3FFFF) == 0x92345
    assert merge_ppn(0x80000, 0x1234567, 0x7FFFFFF) == 0x1234567
    clean = dict(cf=0, cfs=[0] * 8, id=1)
    for field, bad in (("cf", 1), ("cfs", [0] * 7 + [1]), ("id", 2)):
        check_response(clean, cf=0, cfs=[0] * 8, request_id=1)
        with pytest.raises(AssertionError):
            check_response(clean | {field: bad}, cf=0, cfs=[0] * 8, request_id=1)
