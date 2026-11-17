"""Legal and corrupt response controls for the extracted FIL-02/FIL-05 checker."""
import pytest

from suites.memblock.mmu.testbenches.ptwfilter.checker import check_single_response
from suites.memblock.mmu.testbenches.ptwfilter.model import s1_values, staged_values
from suites.memblock.mmu.testbenches.ptwfilter.transactions import Req

pytestmark = pytest.mark.selftest


def test_single_completion_rejects_bad_identity_or_payload():
    assert s1_values(0x10000)["s1_entry_tag"] == 0x2000
    assert staged_values(Req(0x10000, 2), vmid=5)["s2_entry_tag"] == 0x10000
    assert staged_values(Req(0x10000, 2), vmid=5)["s2_entry_vmid"] == 5
    clean = dict(valid=1, s2xlate=0, s1_entry_tag=0x2000, s1_entry_ppn=0x12345,
                 valididx=[1] * 8, ppn_low=list(range(8)))
    for field, bad in (("valid", 0), ("s2xlate", 2), ("s1_entry_tag", 0x2001),
                       ("s1_entry_ppn", 0x12344), ("valididx", [0] * 8),
                       ("ppn_low", [0] * 8)):
        check_single_response(clean, 0x10000, 0x12345)
        with pytest.raises(AssertionError):
            check_single_response(clean | {field: bad}, 0x10000, 0x12345)
