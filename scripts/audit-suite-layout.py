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

Signal operations and exposed native handles are reported separately from
physical-name counts. Renaming .dut to .raw_dut or returning a pin dictionary
must not make the transaction report green.

Functional access to an owner's driver/ports/model/monitor or private encoding
and timing helpers is separate infrastructure coupling, even without physical
field names. This remains a conservative syntax report, not a dataflow proof.

Explicit pytest selftest markers are reported separately, as are the existing
selftest directories. Mixed files keep unmarked tests and helpers in the
functional scan. Classification is visible in JSON and needs semantic review;
neither a marker nor coverage=False proves that a test is a genuine self-check.
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
SELECT_DIRS = {'bundle', 'drivers', 'monitors', 'scoreboard', 'model', 'framework',
               'diagnostics', 'checkers', 'selftest', 'tools'}
OWNER_SUFFIXES = ('_agent', '_env', '_dut', '_harness')
LEGACY_PACKAGES = {name+'verify' for name in
                   ('bpu','ftq','icache','ifu','dcache','lsq','lsu','mmu','sbuffer','vagq')}
SOURCE_SKIP = {'dut','rtl','results','XiangShan','__pycache__','.pytest_cache'}


def source_tree(path):
    return path if isinstance(path, ast.AST) else ast.parse(path.read_text(encoding='utf-8'))


def selftest_scopes(tree):
    """Partition literal pytest classifications without importing test code.

    Only the canonical pytest.mark.selftest spelling is recognized. Dynamic
    marker expressions stay in the functional scan. Helpers in a mixed module
    or class stay there too, even if a marked test happens to call them.
    """
    def marked(value):
        if isinstance(value, (ast.List, ast.Tuple)):
            return any(marked(item) for item in value.elts)
        if isinstance(value, ast.Call):
            value = value.func
        return (isinstance(value, ast.Attribute) and value.attr == 'selftest'
                and isinstance(value.value, ast.Attribute) and value.value.attr == 'mark'
                and isinstance(value.value.value, ast.Name) and value.value.value.id == 'pytest')

    def scope_marker(body):
        assignments = []
        for node in body:
            targets = (node.targets if isinstance(node, ast.Assign) else
                       [node.target] if isinstance(node, ast.AnnAssign) else [])
            references = [child for child in ast.walk(node)
                          if isinstance(child, ast.Name) and child.id == 'pytestmark']
            if references:
                # Reassignment, augmented/conditional or computed markers are
                # not sufficient evidence for excluding a scope. Reads could
                # hand the list to mutating code; del/clear also remove marks.
                if (len(references) != 1
                        or not isinstance(references[0].ctx, ast.Store)
                        or not any(target is references[0] for target in targets)):
                    return False
                assignments.append(node.value)
        return len(assignments) == 1 and marked(assignments[0])

    classified = []

    def partition(node, prefix=''):
        name = prefix + getattr(node, 'name', '<module>')
        is_test = (isinstance(node, ast.Module)
                   or isinstance(node, ast.ClassDef) and node.name.startswith('Test')
                   or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'))
        if is_test and (any(marked(item) for item in getattr(node, 'decorator_list', []))
                        or isinstance(node, (ast.Module, ast.ClassDef)) and scope_marker(node.body)):
            classified.append({'scope': name, 'line': getattr(node, 'lineno', 1),
                               'reason': 'explicit-selftest-marker'})
            return None, node
        if not isinstance(node, (ast.Module, ast.ClassDef)):
            return node, None
        feature, selftest = copy.copy(node), copy.copy(node)
        feature.body, selftest.body = [], []
        for child in node.body:
            ordinary, control = partition(child, '' if isinstance(node, ast.Module) else name + '.')
            if ordinary is not None:
                feature.body.append(ordinary)
            if control is not None:
                selftest.body.append(control)
        return feature, selftest if selftest.body else None

    feature, selftest = partition(tree)
    empty = ast.Module(body=[], type_ignores=[])
    if selftest is not None and selftest is not tree:
        # Keep imported P aliases visible to the physical-field detector.
        selftest.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))] + selftest.body
    return feature or empty, selftest or empty, classified


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
    tree = source_tree(path)
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


def signal_accesses(path):
    """Find explicit signal operations, without treating response.value as a pin.

    This is a conservative syntax check, not dataflow or protocol certification.
    Keep the locations visible so unusual user-defined methods can be reviewed.
    """
    tree=source_tree(path)
    operations={'Set','U','Get','AsImmWrite','AsRiseWrite','IsInIO','IsOutIO',
                'RefreshComb','Step','GetKeys','GetXClock'}
    handles={'raw_dut','xport','xclock'}
    hits=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in operations:
            hits.append({'line':node.lineno,'kind':'signal-operation','expression':ast.unparse(node.func)})
        elif isinstance(node,ast.Attribute) and node.attr in handles:
            hits.append({'line':node.lineno,'kind':'native-handle','expression':ast.unparse(node)})
    return sorted(hits,key=lambda hit:(hit['line'],hit['expression']))


def component_accesses(path):
    """Find explicit owner-infrastructure bypasses and simple owner aliases.

    An imported standalone reference model or an immutable response's ordinary
    fields are not an agent's mutable checker state. Owner names follow the
    fixture convention; this check cannot certify arbitrary dynamic aliases.
    """
    tree=source_tree(path)
    owners={'agent','env','harness','dut'}
    owners.update(node.id for node in ast.walk(tree)
                  if isinstance(node,ast.Name) and is_owner(node.id))

    def owner(value):
        if isinstance(value,ast.Name):
            return value.id in owners
        if isinstance(value,(ast.Attribute,ast.Subscript)):
            return owner(value.value)
        return False

    # Only a plain assignment of the owner itself carries its identity. A
    # response obtained through a transaction method is deliberately not an
    # owner alias, even if its fields happen to have infrastructure-like names.
    changed=True
    while changed:
        changed=False
        for node in ast.walk(tree):
            targets=(node.targets if isinstance(node,ast.Assign) else
                     (node.target,) if isinstance(node,ast.AnnAssign) else ())
            value=getattr(node,'value',None)
            if isinstance(value,ast.Name) and value.id in owners:
                for target in targets:
                    if isinstance(target,ast.Name) and target.id not in owners:
                        owners.add(target.id)
                        changed=True

    def kind(name):
        if name in {'ports','bundle','driver','monitor','model','checker','reference','scoreboard'}:
            return 'owner-component'
        if name.endswith(('_driver','_monitor','_scoreboard')):
            return 'owner-component'
        if name.startswith('_') and not name.startswith('__'):
            return 'owner-private-helper'
        return None

    hits=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute) and owner(node.value) and kind(node.attr):
            hits.append(dict(line=node.lineno,kind=kind(node.attr),expression=ast.unparse(node)))
        elif (isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
              and node.func.id=='getattr' and len(node.args)>=2 and owner(node.args[0])
              and isinstance(node.args[1],ast.Constant) and isinstance(node.args[1].value,str)
              and kind(node.args[1].value)):
            hits.append(dict(line=node.lineno,kind=kind(node.args[1].value),expression=ast.unparse(node)))
    return sorted(hits,key=lambda hit:(hit['line'],hit['expression']))


def suite_entries():
    for recipe_path in sorted((ROOT / 'suites').glob('*/*/ucv.json')):
        recipe = json.loads(recipe_path.read_text(encoding='utf-8'))
        if 'suite' not in recipe:
            continue
        tests = recipe.get('tests') or ['modules']
        if len(tests) != 1:
            raise SystemExit(f'{recipe_path}: expected exactly one tests root')
        suite_root = recipe_path.parent
        pytest_root = suite_root / recipe.get('pytest_root', '.')
        yield recipe['suite'], suite_root, pytest_root, suite_root / tests[0]


def is_owner(name):
    return name.endswith(OWNER_SUFFIXES)


def root_fixtures(path, seen=None):
    """Statically visible fixture entries, NOT a per-DUT ownership proof.

    Root conftests are registration tables: every fixture function, every
    ``agent_fixture``/``dut_fixture`` assignment and every import from a
    project ``fixtures`` module is a candidate registration entry. Literal
    pytest_plugins declarations are followed without importing the plugins. This may
    include session helpers and cannot establish per-DUT ownership.
    """
    seen=set() if seen is None else seen
    path=path.resolve()
    if path in seen or not path.is_file():
        return set()
    seen.add(path)
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = set()

    def assigned(value):
        if isinstance(value, ast.Call):
            func = ast.unparse(value.func)
            if func.endswith(('agent_fixture', 'dut_fixture')):
                return True
        return False

    for node in tree.body:
        targets=(node.targets if isinstance(node,ast.Assign) else
                 [node.target] if isinstance(node,ast.AnnAssign) else [])
        if any(isinstance(target,ast.Name) and target.id=='pytest_plugins' for target in targets):
            try:
                plugins=ast.literal_eval(node.value)
            except (ValueError,TypeError):
                plugins=[]
            if isinstance(plugins,str):plugins=[plugins]
            if isinstance(plugins,(list,tuple)):
                for plugin in plugins:
                    if not isinstance(plugin,str) or not all(part.isidentifier() for part in plugin.split('.')):
                        continue
                    candidate=ROOT.joinpath(*plugin.split('.'))
                    candidate=(candidate/'__init__.py') if candidate.is_dir() else candidate.with_suffix('.py')
                    if candidate.resolve().is_relative_to(ROOT.resolve()):
                        names.update(root_fixtures(candidate,seen))
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
        tree = source_tree(path)
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
    root_conftest = suite_root / 'conftest.py'
    conftests = sorted(path for path in suite_root.rglob('conftest.py')
                       if 'results' not in path.parts)
    nested = [path for path in conftests if path.resolve() != root_conftest.resolve()]
    owner_fixtures = root_fixtures(root_conftest)
    env_pytest = sorted(suite_root.rglob('env/pytest.py'))
    direct = []
    pin_fields = 0
    pin_level_cases = []
    signal_level_cases = []
    component_level_cases = []
    selftest_cases = []
    feature_cases = 0
    if tests_root.is_dir():
        for path in tests_root.rglob('test_*.py'):
            relative = path.relative_to(tests_root)
            tree = source_tree(path)
            shared = tests_root.name=='testbenches' and relative.parts[:2]==('shared','tests')
            if shared or any(part in SELECT_DIRS for part in relative.parts[:-1]):
                controls = tree
                feature = ast.Module(body=[], type_ignores=[])
                classifications = [{'scope': '<module>', 'line': 1,
                                    'reason': 'shared-tests' if shared else 'selftest-directory'}]
            else:
                feature, controls, classifications = selftest_scopes(tree)
            if classifications:
                selftest_cases.append({'path': str(path.relative_to(suite_root)),
                    'classifications': classifications, 'pin_fields': pin_accesses(controls),
                    'signal_operations': signal_accesses(controls),
                    'component_accesses': component_accesses(controls),
                    'native_accesses': native_access(controls)})
            if not feature.body:
                continue
            feature_cases += 1
            fields = pin_accesses(feature)
            pin_fields += sum(fields.values())
            if any(fields.values()):
                pin_level_cases.append({'path': str(path.relative_to(suite_root)), **fields})
            signals=signal_accesses(feature)
            if signals:
                signal_level_cases.append({'path':str(path.relative_to(suite_root)),'hits':signals})
            components=component_accesses(feature)
            if components:
                component_level_cases.append({'path':str(path.relative_to(suite_root)),'hits':components})
            hits = native_access(feature)
            if hits:
                direct.append({'path': str(path.relative_to(suite_root)), 'hits': hits})
    pytest_ini = suite_root / 'pytest.ini'
    selftest = pytest_ini.is_file() and 'selftest:' in pytest_ini.read_text(encoding='utf-8')
    layout_issues=[]
    if (suite_root/'ucv.json').is_file():
        from ucv.layout import problems
        from ucv.config import Project
        from ucv.workspace import metadata
        target=Project(ROOT).suite(suite)
        layout_issues=problems(target,metadata(target))
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
        'signal_level_cases': signal_level_cases,
        'signal_operations': sum(len(case['hits']) for case in signal_level_cases),
        'component_level_cases': component_level_cases,
        'component_accesses': sum(len(case['hits']) for case in component_level_cases),
        'selftest_cases': selftest_cases,
        'transaction_boundary': 'needs-adapter' if pin_fields or direct or signal_level_cases or component_level_cases else 'no-static-leak-found',
        'namespace': '.'.join(suite_root.relative_to(ROOT).parts),
        'namespace_issues': namespace_problems(suite_root),
        'layout_issues':layout_issues,
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
    problems.extend(row.get('layout_issues',[]))
    if require_transaction_boundary and row['pin_fields']:
        problems.append(f"{row['pin_fields']} pin-level expressions require transaction adapters")
    if require_transaction_boundary and row.get('signal_operations'):
        problems.append(f"{row['signal_operations']} signal operations/native handles require transaction adapters")
    if require_transaction_boundary and row.get('component_accesses'):
        problems.append(f"{row['component_accesses']} owner infrastructure/private-helper accesses require transaction adapters")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='write the complete audit as JSON')
    parser.add_argument('--strict', action='store_true', help='exit nonzero on structural wiring violations only')
    parser.add_argument('--require-transaction-boundary', action='store_true',
                        help='also reject physical fields, signal operations and owner infrastructure bypasses')
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
    print('| suite | feature files | fixture entries | extra conftest | env/pytest | native access files | pin expressions | signal operations | owner infrastructure | selftest files | selftest | transaction boundary | structural status |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|')
    failed = False
    for row in rows:
        problems = violations(row, require_transaction_boundary=args.require_transaction_boundary)
        failed = failed or bool(problems)
        print(f"| {row['suite']} | {row['feature_testcases']} | {len(row['root_owner_fixtures'])} | "
              f"{len(row['nested_conftests'])} | {row['env_pytest_count']} | "
              f"{len(row['direct_access_cases'])} | {row['pin_fields']} | {row['signal_operations']} | "
               f"{row['component_accesses']} | "
               f"{len(row['selftest_cases'])} | "
              f"{'yes' if row['selftest_marker'] else 'no'} | "
              f"{row['transaction_boundary']} | "
              f"{'; '.join(problems) or 'ok'} |")
    if (args.strict or args.require_transaction_boundary) and failed:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
