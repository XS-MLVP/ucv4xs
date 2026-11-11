"""Matrix input domains and hand history answers; pure, no hardware credit."""
import pytest
from suites.frontend.bpu.testbenches.bpu.model.redirect_matrix import REDIRECT_CASES


@pytest.mark.parametrize('case', REDIRECT_CASES, ids=lambda c: c.label)
def test_physical_bootstrap_and_guarded_virtual_recovery_have_distinct_domains(case):
    assert case.boot_pc < 1 << 32
    assert case.pc < 1 << 49
    assert case.cfi // (1 << 49) == case.guard
    assert (case.boundary['common'] // (1 << 48)) % 2 == case.sign
    assert case.boundary['phr'] == case.cfi
    assert ((16 * ((case.boot_pc + 4) % 512)) ^ ((case.pc // 2) % 32768)) == 0
    if case.taken:
        assert case.next_history(0x123) == (((0x123 << 2) ^ (16 * ((case.pc + 4) & 511)) ^ ((case.target >> 1) & 32767)) & ((1 << 532) - 1))
    else:
        assert case.target == case.pc + 5
        assert case.next_history(0x123) == 0x123
