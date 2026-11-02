"""Moving a testcase must not silently replace its reference model contract."""
import ast
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFT = ROOT / 'suites/memblock/lsq/tests/conftest.py'


def test_primary_lsq_fixtures_do_not_dispatch_by_test_path():
    tree = ast.parse(CONFT.read_text())
    functions = {node.name: node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert 'raw' in functions and 'replay' in functions
    assert not {'root_raw', 'root_replay', '_test_path', 'lsq'} & functions.keys()
    registration = next(node for node in tree.body if isinstance(node, ast.ImportFrom)
                        and node.module == 'suites.memblock.lsq.lsq_wrapper.fixtures')
    assert ('wrapper_lsq', 'lsq') in {(item.name, item.asname) for item in registration.names}
    # Dynamic access to the Toffee registration hook is unrelated to selecting
    # an oracle and remains allowed in dut_factory.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'getfixturevalue':
            assert len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
            assert node.args[0].value == 'toffee_register_dut'


@pytest.mark.parametrize('directory,expected', [
    ('local_reset', {'local_reset_lsq'}),
    ('sq_endpoint', {'sq_raw', 'sq_replay', 'sq_lsq'}),
])
def test_alternate_contracts_are_explicit_test_dependencies(directory, expected):
    found = set()
    for path in (CONFT.parent / directory).glob('test_*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                args = {arg.arg for arg in node.args.args}
                assert not args & {'raw', 'replay', 'lsq'}, (path, node.name)
                found |= args & expected
    assert found == expected


def test_root_fixture_registration_survives_arbitrary_test_directory(tmp_path):
    """Use real pytest fixture discovery with inert models, not native credit."""
    source = '''import pytest
@pytest.fixture
def wrapper_lsq(): return 'primary-wrapper-model'
@pytest.fixture
def sq_lsq(): return 'exclusive-tail-model'
@pytest.fixture
def local_reset_lsq(): return 'retained-external-model'
'''
    package = tmp_path / 'sentinel_models.py'
    package.write_text(source)
    tree = ast.parse(CONFT.read_text())
    # Freeze the actual root import alias, substituting only its module path.
    alias = next(node for node in tree.body if isinstance(node, ast.ImportFrom)
                 and node.module == 'suites.memblock.lsq.lsq_wrapper.fixtures')
    imported = [item for item in alias.names if item.name == 'wrapper_lsq'][0]
    (tmp_path / 'conftest.py').write_text(
        f'from sentinel_models import {imported.name} as {imported.asname}, sq_lsq, local_reset_lsq\n')
    for directory in ('sq_endpoint', 'local_reset', 'moved_elsewhere'):
        tests = tmp_path / directory
        tests.mkdir()
        (tests / 'test_contract.py').write_text('''def test_contract(lsq, sq_lsq, local_reset_lsq):
    assert lsq=='primary-wrapper-model'
    assert sq_lsq=='exclusive-tail-model'
    assert local_reset_lsq=='retained-external-model'
''')
    result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                             '--import-mode=importlib',
                             '--confcutdir=' + str(tmp_path), str(tmp_path)],
                            cwd=tmp_path, text=True, capture_output=True, timeout=60,
                            env={**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                                 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stdout + result.stderr
    assert '3 passed' in result.stdout
