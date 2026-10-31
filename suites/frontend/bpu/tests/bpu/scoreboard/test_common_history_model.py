"""Independent arithmetic/path checks, no DUT and no hardware observations."""
from itertools import product
import pytest
from suites.frontend.bpu.bpu.model.phr.model import path_hash
from suites.frontend.bpu.bpu.model.sc.common_state import backwards
from suites.frontend.bpu.bpu.model.sc.common_state import dedup
from suites.frontend.bpu.bpu.model.sc.common_state import recovery
from suites.frontend.bpu.bpu.model.sc.common_state import shifted
from suites.frontend.bpu.bpu.model.sc.common_state import update
from suites.frontend.bpu.bpu.case.sc.nonzero_scenarios import recipe


@pytest.mark.parametrize('bank,direction', tuple(product((0, 1), ('forward', 'backward'))))
def test_real_branch_path_has_zero_PHR_hash_but_nonzero_common_history(bank, direction):
    plan = recipe(bank, direction)
    assert path_hash(plan['prefix'] + 2, plan['prefix_target']) == 0
    assert path_hash(plan['jump'], plan['target']) == 0
    assert backwards(plan['prefix'] + 2, plan['prefix_target']) == (direction == 'backward')
    actual = update(dict(valid=0, ghr=0, bw=0), [2, 0, 0, 0], [1, 0, 0, 0],
        dict(pc=plan['prefix'], position=2, target=plan['prefix_target'], taken=1, branch_type=1), 0)
    assert actual == {key: plan['expected'][key] for key in ('valid', 'ghr', 'bw')}


@pytest.mark.parametrize('old', tuple(range(256)))
def test_GHR_shift_truncation_and_conditional_bit(old):
    for less, hits, taken, conditional in product(range(5), range(5), (0, 1), (0, 1)):
        expected = (old * 2 ** (less if taken else hits)) % 256
        if taken and conditional:
            expected = (2 * expected + 1) % 256
        assert shifted(old, less, hits, taken, conditional, taken, 8) == expected


@pytest.mark.parametrize('old', tuple(range(16)))
def test_BW_only_appends_actual_conditional_backward_bit(old):
    for less, hits, taken, conditional, bit in product(range(5), range(5), (0, 1), (0, 1), (0, 1)):
        expected = (old * 2 ** (less if taken else hits)) % 16
        if taken and conditional:
            expected = (2 * expected + bit) % 16
        assert shifted(old, less, hits, taken, conditional, bit, 4) == expected


@pytest.mark.parametrize('mask,positions,expected', (
    ([1, 1, 1, 1], [4, 4, 7, 7], [1, 0, 1, 0]),
    ([0, 1, 1, 1], [4, 4, 7, 7], [0, 1, 1, 0]),
    ([1, 1, 1, 1], [7, 2, 4, 1], [1, 1, 1, 1]),
    ([0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0]),
))
def test_conditional_position_dedup(mask, positions, expected):
    assert dedup(mask, positions) == expected


@pytest.mark.parametrize('taken,branch_type,target', tuple(product((0, 1), (1, 2), (0x40000100, 0x40000300))))
def test_redirect_uses_captured_history_and_actual_branch(taken, branch_type, target):
    redirect = dict(taken=taken, branch_type=branch_type, target=target, cfi_pc=0x40000204,
        meta=dict(ghr=0x91, bw=9, hits=[1, 1, 0, 1], positions=[1, 3, 7, 6]))
    base_ghr = (0x91 << (2 if taken else 3)) & 255
    base_bw = (9 << (2 if taken else 3)) & 15
    if taken and branch_type == 1:
        base_ghr = (2 * base_ghr + 1) & 255
        base_bw = (2 * base_bw + int(target < 0x40000204)) & 15
    assert recovery(redirect) == dict(valid=0, ghr=base_ghr, bw=base_bw)
