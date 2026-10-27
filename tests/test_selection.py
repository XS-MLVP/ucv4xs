"""Explicit cases replace recipe defaults, using pytest's real collection. MPL-2.0."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from ucv.run import collection_arguments


@pytest.mark.parametrize('arguments,expected', [
    ([], ['test_drop', 'test_keep']),
    (['tests/test_keep.py::test_keep'], ['test_keep']),
    (['-k', 'keep'], ['test_keep']),
])
def test_actual_collection_honors_explicit_cases_and_default_filters(tmp_path, arguments, expected):
    suite = tmp_path/'suite with spaces'
    (suite/'tests').mkdir(parents=True)
    (suite/'pytest.ini').write_text('[pytest]\n')
    for name in ('keep', 'drop'):
        (suite/f'tests/test_{name}.py').write_text(f'def test_{name}():\n    pass\n')
    receipt = tmp_path/'receipt'
    spec = SimpleNamespace(path=suite, recipe={'tests':['tests']})
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
           'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src'),
           'UCV_CASE_DIR':str(receipt)}
    command = [sys.executable, '-m', 'pytest', '-q', '--collect-only',
               '-p', 'ucv.pytest_plugin', '-c', str(suite/'pytest.ini'),
               '--rootdir='+str(suite), *collection_arguments(spec), *arguments]
    result = subprocess.run(command, cwd=suite, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout+result.stderr
    record = json.loads((receipt/'cases.json').read_text())
    assert sorted(node.split('::')[-1] for node in record['collected']) == expected
    assert record['collect_only'] and not record['cases']
