import ucv.runtime as ucv_paths
"""A stale PYTHONPATH or copied native binding must fail before simulation."""
from pathlib import Path
import ast
import json
from types import SimpleNamespace

import pytest
import toffee
import xspcomm

from bpuverify.common.env.runtime import validate_dut_runtime, validate_runtime
from bpuverify.common.env.paths import REPO_ROOT


def test_runtime_uses_the_project_environment_and_native_protocol():
    actual = validate_runtime()
    assert actual['native_abi'] == 3
    assert actual['coverage_protocol'] == 5
    expected = ucv_paths.project_root() / '.venv'
    assert Path(actual['toffee']).is_relative_to(expected)
    validate_dut_runtime(xspcomm)


def test_old_toffee_checkout_is_not_a_silent_fallback(monkeypatch):
    monkeypatch.setattr(toffee, '__file__', str(ucv_paths.project_root() / '.tools/sources/toffee/src/toffee/__init__.py'))
    with pytest.raises(RuntimeError, match='project environment'):
        validate_runtime()


@pytest.mark.parametrize('method,value', [('abi_version', 1), ('version', '0.1.0')])
def test_old_copied_dut_bindings_are_rejected(monkeypatch, method, value):
    monkeypatch.setattr(xspcomm, method, lambda: value)
    with pytest.raises(RuntimeError, match='Native runtime mismatch'):
        validate_dut_runtime(xspcomm)


def test_port_bindings_do_not_depend_on_generated_hierarchy_injections():
    for path in (REPO_ROOT / 'bpuverify').glob('*/bundle/ports.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            assert not (isinstance(node, ast.Attribute) and node.attr == 'io'
                        and isinstance(node.value, ast.Name) and node.value.id == 'dut'), path
    source = (REPO_ROOT / 'bpuverify/common/bundle/bindings.py').read_text()
    assert 'dut.signal_tree' not in source
    assert 'Bundle.bind_tree' in source


def test_incomplete_copied_package_is_rejected_before_dut_construction():
    with pytest.raises(RuntimeError, match='incomplete xcomm bindings'):
        validate_dut_runtime(SimpleNamespace())


def test_project_native_pin_matches_target_framework_ci():
    project = json.loads((ucv_paths.project_root() / 'dependencies/versions.json').read_text())['xcomm']
    upstream = json.loads((ucv_paths.project_root() / '.tools/sources/toffee/.github/native-dependencies.json').read_text())['xcomm']
    assert project['commit'] == upstream['ref']
    assert all(project[key] == upstream[key] for key in ('package_version', 'native_abi', 'coverage_protocol'))


@pytest.fixture(autouse=True)
def clear_runtime_validation_cache():
    validate_runtime.cache_clear()
    yield
    validate_runtime.cache_clear()
