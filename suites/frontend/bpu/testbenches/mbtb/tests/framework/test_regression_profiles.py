"""Scope changes collection, never silently skip tests or shrink schemas."""
from types import SimpleNamespace
import subprocess
import sys

import pytest

from suites.frontend.bpu.testbenches.mbtb.tests import regression as mbtb_regression


@pytest.mark.parametrize('profile,count', [('production', 2), ('physical', 256)])
def test_mbtb_index_scope_has_zero_and_maximum_without_losing_physical_indices(profile, count):
    indices = mbtb_regression.mbtb_replacement_indices(profile)
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
    mbtb_regression.pytest_generate_tests(metafunc)
    (names, indices), options = calls.pop()
    assert names == 'index' and len(indices) == count
    assert options['ids'] == [f'index{index}' for index in indices]


@pytest.mark.parametrize('profile,count', [('production', 32), ('physical', 4096)])
def test_real_mbtb_collection_is_independently_schedulable_with_no_skips(profile, count):
    root = __import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--collect-only', f'--regression-profile={profile}',
        'testbenches/mbtb/tests/testcase/test_replacement_indices.py'],
        cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = [line for line in result.stdout.splitlines() if line.startswith('testbenches/') and '::' in line]
    assert len(nodes) == len(set(nodes)) == count
    assert not any('skipped' in line for line in result.stdout.splitlines())
