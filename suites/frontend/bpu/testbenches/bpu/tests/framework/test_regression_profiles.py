"""Scope changes collection, never silently skip tests or shrink schemas."""
from types import SimpleNamespace
from pathlib import Path
import subprocess
import sys

import pytest

from suites.frontend.bpu.testbenches.bpu.tests import regression


@pytest.mark.parametrize('profile,count', [('production', 1), ('physical', 256)])
def test_profile_coordinates_are_explicit_and_deterministic(profile, count):
    coordinates = regression.counter_coordinates(profile)
    assert len(coordinates) == len(set(coordinates)) == count
    assert (0, 0) in coordinates
    if profile == 'physical':
        assert set(coordinates) == {(bank, entry_set) for bank in range(4) for entry_set in range(64)}


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
    root = __import__('suites.frontend.bpu', fromlist=['ROOT']).ROOT
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
        '--collect-only', f'--regression-profile={profile}',
        'testbenches/bpu/tests/testcase/test_integrated_abtb_counters.py'],
        cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    nodes = [line for line in result.stdout.splitlines() if line.startswith('testbenches/') and '::' in line]
    assert len(nodes) == len(set(nodes)) == count
    assert len({node.split('[')[0] for node in nodes}) == 3
    assert not any('skipped' in line for line in result.stdout.splitlines())
