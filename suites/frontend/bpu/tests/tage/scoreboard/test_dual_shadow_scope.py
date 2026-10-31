"""Explicit scope and hand-derived dual-write phase expectations."""
from itertools import product

import pytest

from suites.frontend.bpu.tage.coverage.dual import DUAL_MODES
from suites.frontend.bpu.tage.coverage.dual import tage_dual_shadow_coverage_model
from suites.frontend.bpu.tage.case.dual_shadow_scenario import expected_witnesses
from suites.frontend.bpu.tage.case.dual_shadow_scenario import validate_case


@pytest.mark.parametrize('mode', DUAL_MODES)
def test_independent_phase_expectations_qualify_owner_depth_hit_and_saturation(mode):
    for bank, depth in product(range(4), range(4)):
        records = expected_witnesses(bank, depth, mode)
        assert len(records) == (8 if mode.startswith('own_') else 6)
        assert tuple(row['request_port'] for row in records) == (0, 1) * (len(records) // 2)
        assert all(row['bank'] == bank for row in records)
        assert [row['new_counter'] for row in records[-2:]] == [0, 7]
        assert all(row['request_counter'] == (1, 6)[row['request_port']] for row in records)
        if mode.startswith('cross_'):
            assert all(row['owner'] == 1 - row['request_port'] for row in records)
            assert [row['old_counter'] for row in records[:2]] == [2, 5]
            assert all(row['hit'] == 1 and row['depth'] == depth for row in records)
        elif mode.startswith('own_'):
            assert [row['hit'] for row in records[:2]] == [int(depth == 0)] * 2
            assert [row['new_counter'] for row in records[:2]] == [1, 6]
        elif mode in ('companion_miss', 'companion_miss_saturated'):
            assert [row['hit'] for row in records[:2]] == [1, 0]
            assert [row['old_counter'] for row in records[:2]] == [
                int(mode == 'companion_miss'), 7]
            assert [row['new_counter'] for row in records[:2]] == [0, 6]
        else:
            assert [row['hit'] for row in records[:2]] == [0, 1]
            assert [row['dirty'] for row in records[:2]] == [0, int(mode == 'companion_dirty_hit')]
        if mode.endswith('_clean'):
            assert all(row['dirty'] == 0 for row in records)
            assert all(row['ready'] == 1 for row in (records[2:] if mode.startswith('own_') else records))
        else:
            assert all(row['ready'] == 0 for row in records)


@pytest.mark.parametrize('bank,depth,mode', ((-1, 0, DUAL_MODES[0]), (4, 0, DUAL_MODES[0]),
    (0, -1, DUAL_MODES[0]), (0, 4, DUAL_MODES[0]), (0, 0, 'ready_valid'),
    (None, 0, DUAL_MODES[0]), (0, None, DUAL_MODES[0])))
def test_unsupported_scope_is_rejected_before_native_preparation(bank, depth, mode):
    with pytest.raises(ValueError, match='unsupported TAGE dual-shadow'):
        validate_case(bank, depth, mode)


def test_coverage_requires_all_banks_depths_modes_and_three_checked_phases():
    coverage = tage_dual_shadow_coverage_model()
    with pytest.raises(AssertionError):
        coverage.assert_coverage(100.0)
    for bank, depth, mode, phase in product(range(4), range(4), DUAL_MODES,
                                           ('native', 'forward', 'reverse')):
        if (bank, depth, mode, phase) != (3, 3, DUAL_MODES[-1], 'reverse'):
            coverage.sample(dict(bank=bank, depth=depth, mode=mode, phase=phase))
    with pytest.raises(AssertionError):
        coverage.assert_coverage(100.0)
    coverage.sample(dict(bank=3, depth=3, mode=DUAL_MODES[-1], phase='reverse'))
    coverage.assert_coverage(100.0)
