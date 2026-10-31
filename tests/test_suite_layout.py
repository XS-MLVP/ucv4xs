"""Structural checks must not disguise pin aliases as transaction migration."""
import functools
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'audit_suite_layout', ROOT / 'scripts/audit-suite-layout.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@functools.lru_cache(maxsize=1)
def audit_rows():
    return tuple(AUDIT.audit(*entry) for entry in AUDIT.suite_entries())


def test_every_suite_passes_the_layout_contract():
    problems = {row['suite']: AUDIT.violations(row) for row in audit_rows()}
    assert not {suite: rows for suite, rows in problems.items() if rows}, problems


def test_layout_audit_sees_every_registered_suite():
    assert {row['suite'] for row in audit_rows()} == {
        'bpu', 'ftq', 'icache', 'ifu', 'dcache',
        'lsq', 'lsu', 'mmu', 'sbuffer', 'vagq',
    }


@pytest.mark.parametrize('suite', ['bpu', 'ftq', 'icache', 'ifu', 'dcache',
                                   'lsq', 'lsu', 'mmu', 'sbuffer', 'vagq'])
def test_audit_separates_structure_from_transaction_boundary(suite):
    """Report current debt without requiring it to remain in future code."""
    row = next(row for row in audit_rows() if row['suite'] == suite)
    assert AUDIT.violations(row) == []
    assert row['pin_fields'] == sum(
        fields['literal'] + fields['keyword'] + fields['alias']
        for fields in row['pin_level_cases'])
    expected = 'needs-adapter' if row['pin_fields'] else 'no-static-leak-found'
    assert row['transaction_boundary'] == expected
    assert bool(AUDIT.violations(row, require_transaction_boundary=True)) == bool(row['pin_fields'])


def test_selftest_marker_is_registered_by_every_suite():
    for row in audit_rows():
        assert row['selftest_marker'], row['suite']


@pytest.mark.parametrize('module',['example.common.pins','example.legacy_pins'])
def test_pin_aliases_and_keywords_cannot_evade_audit(tmp_path,module):
    path = tmp_path / 'test_example.py'
    path.write_text(f'from {module} import P as fields'+chr(10)+'''
def test_example(env):
    env.set(io_req_valid=1)
    env.expect({fields.p_req_ready: 1})
    env.read(fields.io(f"response_{0}_valid"))
''')
    assert AUDIT.pin_accesses(path) == {'literal': 0, 'keyword': 1, 'alias': 2}


def test_namespace_audit_rejects_legacy_imports_but_preserves_history(tmp_path):
    (tmp_path/'__init__.py').write_text('')
    (tmp_path/'native.py').write_text('from lsqverify.native import Native'+chr(10))
    (tmp_path/'history.py').write_text('frozen = "lsqverify/native.py"'+chr(10))
    issues=AUDIT.namespace_problems(tmp_path)
    assert len(issues)==1 and 'nonqualified import lsqverify.native' in issues[0]
    (tmp_path/'common').mkdir()
    assert 'obsolete implementation wrapper: common' in AUDIT.namespace_problems(tmp_path)


def test_pin_audit_ignores_prose_not_executable_fields(tmp_path):
    path = tmp_path / 'test_example.py'
    path.write_text('''"""io_documentation_only"""
def test_example(env):
    env.read("io_req_ready")
''')
    assert AUDIT.pin_accesses(path) == {'literal': 1, 'keyword': 0, 'alias': 0}


@pytest.mark.parametrize('suite', ['dcache', 'lsu', 'mmu', 'sbuffer'])
def test_moved_fixture_root_still_resolves_suite_directory(suite):
    import ast
    path = ROOT / 'suites' / 'memblock' / suite / 'tests' / 'conftest.py'
    tree = ast.parse(path.read_text())
    expr = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'ROOT' for t in node.targets))
    actual = eval(compile(ast.Expression(expr), str(path), 'eval'),
                  {'Path': Path, '__file__': str(path)})
    assert actual == path.parents[1]
