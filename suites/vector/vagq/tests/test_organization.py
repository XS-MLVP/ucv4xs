"""Small dependency-boundary guards; not a new component framework."""
import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.toffee_functional_coverage(False)
ROOT = Path(__file__).resolve().parents[1]


def imported_names(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ''


def test_verification_does_not_depend_on_the_bpu_project():
    for directory in ('vagqverify', 'tests'):
        for path in (ROOT / directory).rglob('*.py'):
            assert not any(name == 'bpuverify' or name.startswith('bpuverify.')
                           for name in imported_names(path)), path
    assert '/home/xyl/bpu-verify' not in (ROOT / 'pytest.ini').read_text()


def test_pure_references_do_not_import_simulator_or_protocol_components():
    for relative in ('manager/model.py', 'addrgen/reference.py'):
        names = tuple(imported_names(ROOT / 'vagqverify' / relative))
        assert not any(name.split('.')[0] in ('dut', 'toffee', 'xspcomm', 'bpuverify')
                       or name.endswith(('ports', 'driver', 'monitor', 'encoding')) for name in names)
