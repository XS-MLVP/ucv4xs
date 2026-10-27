"""Scope changes collection, never silently skip tests or shrink schemas."""
from types import SimpleNamespace
from pathlib import Path
import subprocess
import sys

import pytest

from bpuverify.common.pytest import regression


@pytest.mark.parametrize('profile,count', [('production', 1), ('physical', 256)])
def test_profile_coordinates_are_explicit_and_deterministic(profile, count):
    coordinates = regression.counter_coordinates(profile)
    assert len(coordinates) == len(set(coordinates)) == count
    assert (0, 0) in coordinates
    if profile == 'physical':
        assert set(coordinates) == {(bank, entry_set) for bank in range(4) for entry_set in range(64)}


def test_unknown_profile_is_not_a_smaller_fallback():
    with pytest.raises(ValueError, match='unknown regression profile'):
        regression.counter_coordinates('typo')
    with pytest.raises(ValueError, match='unknown regression profile'):
        regression.mbtb_replacement_indices('typo')


@pytest.mark.parametrize('profile,count', [('production', 1), ('physical', 256)])
def test_generate_only_marked_scenarios_without_skips(profile, count):
    calls = []
    metafunc = SimpleNamespace(
        definition=SimpleNamespace(get_closest_marker=lambda name: True),
        config=SimpleNamespace(getoption=lambda name: profile),
        parametrize=lambda *args, **kwargs: calls.append((args, kwargs)))
    regression.pytest_generate_tests(metafunc)
    (names, coordinates), options = calls.pop()
    assert names == 'bank,entry_set' and len(coordinates) == count
    assert options['ids'] == [f'bank{bank}-set{entry_set}' for bank, entry_set in coordinates]
    metafunc.definition.get_closest_marker = lambda name: None
    regression.pytest_generate_tests(metafunc)
    assert calls == []


@pytest.mark.parametrize('profile,count', [('production', 3), ('physical', 768)])
def test_real_pytest_collects_only_the_requested_scope(profile, count):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--collect-only', f'--regression-profile={profile}',
        'tests/bpu/testcase/test_integrated_abtb_counters.py'],
        cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = [line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    assert len(nodes) == len(set(nodes)) == count
    assert len({node.split('[')[0] for node in nodes}) == 3
    assert not any('skipped' in line for line in result.stdout.splitlines())


@pytest.mark.parametrize('profile,count', [('production', 2), ('physical', 256)])
def test_mbtb_index_scope_has_zero_and_maximum_without_losing_physical_indices(profile, count):
    indices = regression.mbtb_replacement_indices(profile)
    assert len(indices) == len(set(indices)) == count
    assert 0 in indices and 255 in indices
    assert indices == ((0, 255) if profile == 'production' else tuple(range(256)))


@pytest.mark.parametrize('profile,count', [('production', 2), ('physical', 256)])
def test_mbtb_generate_tests_marks_only_its_index_axis(profile, count):
    calls = []
    metafunc = SimpleNamespace(
        definition=SimpleNamespace(get_closest_marker=lambda name: name == 'mbtb_replacement_matrix' or None),
        config=SimpleNamespace(getoption=lambda name: profile),
        parametrize=lambda *args, **kwargs: calls.append((args, kwargs)))
    regression.pytest_generate_tests(metafunc)
    (names, indices), options = calls.pop()
    assert names == 'index' and len(indices) == count
    assert options['ids'] == [f'index{index}' for index in indices]


@pytest.mark.parametrize('profile,count', [('production', 32), ('physical', 4096)])
def test_real_mbtb_collection_is_independently_schedulable_with_no_skips(profile, count):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--collect-only', f'--regression-profile={profile}',
        'tests/mbtb/testcase/test_replacement_indices.py'],
        cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = [line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    assert len(nodes) == len(set(nodes)) == count
    assert not any('skipped' in line for line in result.stdout.splitlines())
