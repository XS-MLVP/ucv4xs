#!/usr/bin/env python3.12
"""Audit verification-package layout against the project skill.

The audit is intentionally read-only.  It reports the layout facts that the
skill asks for: one pytest root, per-DUT owner fixtures reachable from that
root, functional testcases that never touch the native DUT or pin collection,
and a separate ``selftest`` marker.

Native access means an actual Python attribute chain. Physical field literals,
io_* keywords and P.p_*/P.io aliases are all pin-level coupling, even when a
harness owns the native DUT. --strict checks structural wiring only; add
--require-transaction-boundary to reject pin-level coupling. Neither mode
certifies monitor ownership, independent oracles or hardware correctness.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SELECT_DIRS = {'bundle', 'drivers', 'monitors', 'scoreboard', 'model', 'framework',
               'diagnostics', 'checkers', 'selftest', 'tools'}
OWNER_SUFFIXES = ('_agent', '_env', '_dut', '_harness')
LEGACY_PACKAGES = {name+'verify' for name in
                   ('bpu','ftq','icache','ifu','dcache','lsq','lsu','mmu','sbuffer','vagq')}
SOURCE_SKIP = {'dut','rtl','results','XiangShan','__pycache__','.pytest_cache'}


def namespace_problems(suite_root):
    """Check implementation imports, not historical path strings in evidence."""
    issues=[]
    if not (suite_root/'__init__.py').is_file():
        issues.append('missing suite namespace initializer')
    for path in suite_root.iterdir():
        if path.is_dir() and (path.name in LEGACY_PACKAGES or path.name == 'common'):
            issues.append('obsolete implementation wrapper: '+path.name)
    for path in suite_root.rglob('*.py'):
        if SOURCE_SKIP & set(path.relative_to(suite_root).parts):
            continue
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names=([node.module or ''] if isinstance(node,ast.ImportFrom) and not node.level
                   else [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
            for name in names:
                if name.split('.')[0] in LEGACY_PACKAGES | {'common'}:
                    issues.append(f'{path.relative_to(suite_root)}:{node.lineno}: nonqualified import {name}')
    return issues


def pin_accesses(path):
    """Count actual expressions, including aliases that hide physical names."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    aliases = {'P'}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or '').endswith(('.pins', '.legacy_pins')):
            aliases.update(alias.asname or alias.name for alias in node.names
                           if alias.name == 'P')
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr)
                  and isinstance(node.body[0].value, ast.Constant)
                  and isinstance(node.body[0].value.value, str)}
    counts = {'literal': 0, 'keyword': 0, 'alias': 0}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and id(node) not in docstrings
                and isinstance(node.value, str) and node.value.startswith('io_')):
            counts['literal'] += 1
        elif isinstance(node, ast.keyword) and node.arg and node.arg.startswith('io_'):
            counts['keyword'] += 1
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
              and node.value.id in aliases and (node.attr.startswith('p_') or node.attr == 'io')):
            counts['alias'] += 1
    return counts


def suite_entries():
    for recipe_path in sorted((ROOT / 'suites').glob('*/*/ucv.json')):
        recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
        if 'suite' not in recipe:
            continue
        tests = recipe.get('tests') or ['tests']
        if len(tests) != 1:
            raise SystemExit(f'{recipe_path}: expected exactly one tests root')
        suite_root = recipe_path.parent
        pytest_root = suite_root / recipe.get('pytest_root', '.')
        yield recipe['suite'], suite_root, pytest_root, suite_root / tests[0]


def is_owner(name):
    return name.endswith(OWNER_SUFFIXES)


def root_fixtures(path):
    """Statically visible fixture entries, NOT a per-DUT ownership proof.

    Root conftests are registration tables: every fixture function, every
    ``agent_fixture``/``dut_fixture`` assignment and every import from a
    project ``fixtures`` module is a candidate registration entry. This may
    include session helpers and cannot establish per-DUT ownership.
    """
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = set()

    def assigned(value):
        if isinstance(value, ast.Call):
            func = ast.unparse(value.func)
            if func.endswith(('agent_fixture', 'dut_fixture')):
                return True
        return False

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (is_owner(target.id) or assigned(node.value)):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if (isinstance(node.target, ast.Name)
                    and (is_owner(node.target.id) or assigned(node.value))):
                names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = {ast.unparse(item) for item in node.decorator_list}
            if any('fixture' in item for item in decorators):
                names.add(node.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                name = alias.asname or alias.name
                if 'fixtures' in module or is_owner(name):
                    if not name.startswith('load_'):
                        names.add(name)
    return names


def native_access(path):
    """Return real native DUT/pin attribute accesses, ignoring prose."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as error:
        return [f'syntax error: {error}']
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in {'dut', 'pins'}:
                hits.add(f'.{node.attr}')
            elif node.attr.startswith('io_'):
                hits.add('io_*')
    return sorted(hits)


def audit(suite, suite_root, pytest_root, tests_root):
    root_conftest = tests_root / 'conftest.py'
    conftests = sorted(path for path in suite_root.rglob('conftest.py')
                       if 'results' not in path.parts)
    nested = [path for path in conftests if path.resolve() != root_conftest.resolve()]
    owner_fixtures = root_fixtures(root_conftest)
    env_pytest = sorted(suite_root.rglob('env/pytest.py'))
    direct = []
    pin_fields = 0
    pin_level_cases = []
    feature_cases = 0
    if tests_root.is_dir():
        for path in tests_root.rglob('test_*.py'):
            relative = path.relative_to(tests_root)
            if any(part in SELECT_DIRS for part in relative.parts[:-1]):
                continue
            feature_cases += 1
            fields = pin_accesses(path)
            pin_fields += sum(fields.values())
            if any(fields.values()):
                pin_level_cases.append({'path': str(path.relative_to(suite_root)), **fields})
            hits = native_access(path)
            if hits:
                direct.append({'path': str(path.relative_to(suite_root)), 'hits': hits})
    pytest_ini = suite_root / 'pytest.ini'
    selftest = pytest_ini.is_file() and 'selftest:' in pytest_ini.read_text(encoding='utf-8')
    return {
        'suite': suite,
        'tests_root': str(tests_root.relative_to(suite_root)),
        'pytest_root': str(pytest_root.relative_to(suite_root)),
        'conftest_count': len(conftests),
        'nested_conftests': [str(path.relative_to(suite_root)) for path in nested],
        'root_owner_fixtures': sorted(owner_fixtures),
        'root_fixture_entries': sorted(owner_fixtures),
        'env_pytest_count': len(env_pytest),
        'selftest_marker': selftest,
        'feature_testcases': feature_cases,
        'direct_access_cases': direct,
        'pin_fields': pin_fields,
        'pin_level_cases': pin_level_cases,
        'transaction_boundary': 'needs-adapter' if pin_fields or direct else 'no-static-leak-found',
        'namespace': '.'.join(suite_root.relative_to(ROOT).parts),
        'namespace_issues': namespace_problems(suite_root),
    }


def violations(row, *, require_transaction_boundary=False):
    problems = []
    if not row['root_owner_fixtures']:
        problems.append('no DUT owner fixture reachable from the pytest root')
    if row['nested_conftests']:
        problems.append(f"{len(row['nested_conftests'])} nested conftest file(s)")
    if row['env_pytest_count']:
        problems.append(f"{row['env_pytest_count']} per-DUT env/pytest.py fixture module(s)")
    if row['direct_access_cases']:
        problems.append(f"{len(row['direct_access_cases'])} functional testcase file(s) access native DUT/pins")
    if not row['selftest_marker']:
        problems.append('no selftest marker')
    problems.extend(row.get('namespace_issues',[]))
    if require_transaction_boundary and row['pin_fields']:
        problems.append(f"{row['pin_fields']} pin-level expressions require transaction adapters")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='write the complete audit as JSON')
    parser.add_argument('--strict', action='store_true', help='exit nonzero on structural wiring violations only')
    parser.add_argument('--require-transaction-boundary', action='store_true',
                        help='also reject physical fields and P.p_*/P.io aliases')
    parser.add_argument('--suite', action='append', dest='suites',
                        help='limit the audit to one suite name; repeat for several')
    args = parser.parse_args(argv)
    entries = list(suite_entries())
    if args.suites:
        known = {entry[0] for entry in entries}
        unknown = set(args.suites) - known
        if unknown:
            parser.error(f'unknown suite(s): {", ".join(sorted(unknown))}')
        entries = [entry for entry in entries if entry[0] in set(args.suites)]
    rows = [audit(*entry) for entry in entries]
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({'suites': rows}, indent=2, ensure_ascii=False) + '\n',
                             encoding='utf-8')
    print('| suite | feature files | fixture entries | extra conftest | env/pytest | native access files | pin expressions | selftest | transaction boundary | structural status |')
    print('|---|---:|---:|---:|---:|---:|---:|---|---|---|')
    failed = False
    for row in rows:
        problems = violations(row, require_transaction_boundary=args.require_transaction_boundary)
        failed = failed or bool(problems)
        print(f"| {row['suite']} | {row['feature_testcases']} | {len(row['root_owner_fixtures'])} | "
              f"{len(row['nested_conftests'])} | {row['env_pytest_count']} | "
              f"{len(row['direct_access_cases'])} | {row['pin_fields']} | "
              f"{'yes' if row['selftest_marker'] else 'no'} | "
              f"{row['transaction_boundary']} | "
              f"{'; '.join(problems) or 'ok'} |")
    if (args.strict or args.require_transaction_boundary) and failed:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
