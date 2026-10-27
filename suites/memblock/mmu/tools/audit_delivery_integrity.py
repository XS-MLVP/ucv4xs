"""Evidence-integrity checks; never a substitute for DUT/ISA acceptance."""
from __future__ import annotations

import ast
import collections
import copy
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest_errors(manifest, expected, native):
    errors = []
    if manifest.get('state') != 'committed':
        errors.append('state')
    if manifest.get('coverage_complete') is not True:
        errors.append('coverage_complete')
    if manifest.get('pytest_exitstatus') != 0:
        errors.append('pytest_exitstatus')
    tests = manifest.get('tests', {})
    if tests != {'PASS': expected} or expected <= 0:
        errors.append('outcomes')
    workers = manifest.get('workers', [])
    if not workers or any(len(w.get('receipt_sha256', '')) != 64 for w in workers):
        errors.append('worker receipts')
    inputs = sum(a.get('input_files', 0) for a in manifest.get('artifacts', [])
                 if a.get('kind') == 'native')
    if inputs != (expected if native else 0):
        errors.append('native inputs')
    return errors


def drift_errors(before, after, current, approvals, dependencies):
    errors = []
    if before != after:
        errors.append('source changed during run')
    differences = {p for p in set(after) | set(current) if after.get(p) != current.get(p)}
    if differences != set(approvals):
        errors.append('unreviewed source drift')
    for path, approval in approvals.items():
        if approval.get('old_sha256') != after.get(path) or approval.get('current_sha256') != current.get(path):
            errors.append('approval digest mismatch: ' + path)
        if not approval.get('reason'):
            errors.append('missing drift reason: ' + path)
        if path in dependencies and approval.get('kind') != 'inventory-metadata-only':
            errors.append('runtime dependency changed: ' + path)
    return errors


def local_dependencies(root, selectors):
    """Conservative local import closure, including every conftest fixture import."""
    todo = [root / 'conftest.py', root / 'tools/run.py']
    for selector in selectors:
        target = root / selector.split('::', 1)[0]
        todo.extend(target.rglob('*.py') if target.is_dir() else [target])
    seen = set()
    while todo:
        path = todo.pop()
        if not path.is_file() or path.suffix != '.py' or path in seen:
            continue
        seen.add(path)
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = list(path.relative_to(root).parent.parts)
                    base = base[:len(base) - node.level + 1]
                    module = '.'.join(base + ([node.module] if node.module else []))
                else:
                    module = node.module or ''
                modules = [module] + [module + '.' + alias.name for alias in node.names]
            for module in modules:
                parts = module.split('.')
                for count in range(1, len(parts) + 1):
                    base = root.joinpath(*parts[:count])
                    for candidate in [base.with_suffix('.py'), base / '__init__.py']:
                        if candidate.is_file() and candidate not in seen:
                            todo.append(candidate)
    return {str(path.relative_to(root)) for path in seen} | {
        'pytest.ini', 'manifest/toolchain.json', 'manifest/pma-reset-reference.json'}


def audit_logic(source):
    """Ignore only the two reviewed inventory metadata fields, not check logic."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict':
            if any(k.arg == 'assertions' for k in node.keywords) and any(k.arg == 'helper_calls' for k in node.keywords):
                node.keywords = [k for k in node.keywords if k.arg not in ('category', 'review')]
    return ast.dump(tree, include_attributes=False)


def selftest():
    """Fail-closed mutation checks of these new integrity predicates."""
    good = {'state': 'committed', 'coverage_complete': True, 'pytest_exitstatus': 0,
            'tests': {'PASS': 2}, 'workers': [{'receipt_sha256': 'a' * 64}],
            'artifacts': [{'kind': 'native', 'input_files': 2}]}
    assert not manifest_errors(good, 2, True)
    count = 1
    for field, bad in [('state', 'pending'), ('coverage_complete', False),
                       ('pytest_exitstatus', 1), ('tests', {'PASS': 1, 'XFAIL': 1}),
                       ('tests', {'PASS': 1, 'SKIP': 1}), ('tests', {'PASS': 1}),
                       ('workers', []), ('artifacts', [])]:
        value = copy.deepcopy(good)
        value[field] = bad
        assert manifest_errors(value, 2, True), field
        count += 1
    before = {'test.py': 'a', 'tool.py': 'b'}
    current = {'test.py': 'a', 'tool.py': 'c'}
    approved = {'tool.py': {'old_sha256': 'b', 'current_sha256': 'c',
                            'reason': 'non-runtime checker', 'kind': 'offline-tool'}}
    assert not drift_errors(before, before, current, approved, {'test.py'})
    count += 1
    for args in [(before, current, current, approved, {'test.py'}),
                 (before, before, current, {}, {'test.py'}),
                 (before, before, current, approved, {'tool.py'}),
                 (before, before, {**current, 'test.py': 'z'}, approved, {'test.py'})]:
        assert drift_errors(*args)
        count += 1
    a = 'def f():\n return dict(assertions=[],helper_calls=[],category=1,review=2)\n'.replace('\n', chr(10))
    b = a.replace('category=1', 'category=9')
    assert audit_logic(a) == audit_logic(b)
    assert audit_logic(a) != audit_logic(a.replace('assertions=[]', 'assertions=[False]'))
    count += 2
    return {'status': 'PASS', 'checks': count, 'scope': 'delivery integrity predicates only; no DUT regression'}


def audit(root):
    root = Path(root)
    ev = root / 'docs/reports/evidence/soundness-20261025'
    index = json.loads((ev / 'final-runs.json').read_text())
    plan = json.loads((ev / 'final-run-plan.json').read_text())
    drift = json.loads((ev / 'source-drift-review.json').read_text())
    collected = json.loads((ev / 'collection.json').read_text())
    residuals = json.loads((ev / 'final-residuals.json').read_text())
    failures, details = [], {}
    checks = 0
    cache = {}

    def require(ok, message):
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(message)

    def hashed(path, expected, message):
        path = Path(path)
        if path not in cache and path.is_file():
            cache[path] = digest(path)
        require(cache.get(path) == expected, message)

    ids = collected['nodeids']
    require(len(ids) == len(set(ids)) == collected['count'] == collected['unique'], 'collection duplicate/count')
    require(set(index['runs']) == set(plan) == set(drift['runs']), 'run selection mismatch')
    total = collections.Counter()
    assigned = []
    for key, row in index['runs'].items():
        run = root / 'results' / row['run']
        manifest = json.loads((run / 'manifest.json').read_text())
        source = json.loads((run / 'verification-sources.json').read_text())
        selectors = plan[key]['tests']
        nodeids = [n for n in ids if any(n.split('::', 1)[0] == p or
                   n.split('::', 1)[0].startswith(p.rstrip('/') + '/') for p in selectors)]
        assigned += nodeids
        require(not manifest_errors(manifest, len(nodeids), key != 'checker-selftest'), key + ': run status/receipts/outcomes')
        require(manifest['tests'] == row['tests'], key + ': index outcomes')
        total.update(manifest['tests'])
        for filename, field in [('manifest.json', 'manifest_sha256'),
                                ('verification-sources.json', 'verification_sources_sha256'),
                                ('trace-policy.json', 'trace_policy_sha256')]:
            hashed(run / filename, row[field], key + ': ' + filename + ' hash')
        require(source.get('seed') == row['seed'] == 1 and source.get('stable_during_run') is True, key + ': seed/stability')
        require(source['command'] == drift['runs'][key]['command'], key + ': command review')
        paths = set(source['sources'])
        # New offline delivery files are not retroactively added to historical snapshots.
        current = {p: digest(root / p) if (root / p).is_file() else None for p in paths}
        dependencies = local_dependencies(root, selectors)
        require(dependencies == set(drift['runs'][key]['dependencies']), key + ': dependency review stale')
        require(dependencies <= paths, key + ': missing runtime dependency snapshot')
        require(not drift_errors(source['sources_before'], source['sources'], current,
                                drift['runs'][key]['differences'], dependencies), key + ': source drift')
        policy = json.loads((run / 'trace-policy.json').read_text())
        require(policy['status'] == 'PASS' and not policy['runtime_set_waveform'] and
                not policy['per_cycle_signal_dump'] and not policy['per_cycle_transaction_dump'] and
                not policy['stray_waveforms_in_run'] and not policy['per_cycle_files'], key + ': trace policy')
        require(not any(run.rglob('*.fst')) and not any(run.rglob('*.vcd')) and
                not any(run.rglob('*.jsonl')), key + ': waveform/per-cycle artifact')
        for artifact in manifest['artifacts']:
            path = Path(artifact['path'])
            hashed(path, artifact['sha256'], key + ': artifact ' + artifact['kind'])
            require(path.is_file() and path.stat().st_size == artifact['size'], key + ': artifact size')
            if artifact['kind'] == 'native':
                build = artifact['build']
                for name, expected in build['files'].items():
                    hashed(name, expected, key + ': DUT build file ' + name)
                hashed(build['processor'], build['processor_sha256'], key + ': coverage processor')
        if key != 'checker-selftest':
            a = json.loads((run / 'coverage-audit.json').read_text())
            hashed(run / 'coverage-audit.json', row['coverage_audit_sha256'], key + ': coverage audit hash')
            metrics = {'line': [a['lcov_lines_dut_only']['covered_lines'], a['lcov_lines_dut_only']['unique_lines']],
                       'toggle': [a['toggles']['covered'], a['toggles']['total']],
                       'branch': [a['branches']['covered'], a['branches']['total']]}
            require(metrics == row['metrics'], key + ': exact coverage metrics')
            native = next(x for x in manifest['artifacts'] if x['kind'] == 'native')
            lcov = next(x for x in manifest['artifacts'] if x['kind'] == 'lcov')
            require(a['coverage_dat_sha256'] == native['sha256'] and
                    a['coverage_info_sha256'] == lcov['sha256'], key + ': audit coverage input identity')
            for name, value in a['source_files'].items():
                hashed(name, value['sha256'], key + ': coverage RTL source ' + name)
            report = json.loads((root / row['build_report']).read_text())
            hashed(root / row['build_report'], row['build_report_sha256'], key + ': build report hash')
            require(report['ok'] and report['dut'] == key, key + ': build report identity')
            for name, expected in report['rtl_sha256'].items():
                hashed(root / 'rtl' / key / name, expected, key + ': build RTL ' + name)
            top_name = report['export_name'] + '.v'
            expected_top = report['rtl_sha256'][report['top'] + '.sv']
            require(native['build']['files'].get(str(root / 'dut' / key / top_name)) == expected_top, key + ': generated top RTL identity')
            functional = json.loads((run / 'functional-coverage.json').read_text())
            require(bool(functional['groups']) and all(g.get('samples', 0) > 0 and g.get('coverage') == 100.0
                    for g in functional['groups']), key + ': sampled functional bins or samples')
            r = residuals['modules'][key]
            require(r['run'] == row['run'] and r['uncovered_lines'] == a['lcov_lines_dut_only']['uncovered']
                    and r['uncovered_toggles'] == a['toggles']['uncovered'] and r.get('disposition', '').startswith('OPEN'), key + ': residual disclosure')
        details[key] = {'run': row['run'], 'pass': len(nodeids),
                        'postrun_differences': sorted(drift['runs'][key]['differences']),
                        'runtime_dependencies': len(dependencies)}
    require(collections.Counter(assigned) == collections.Counter(ids), 'collection partition incomplete/overlapping')
    require(dict(total) == index['totals'] == {'PASS': collected['count']}, 'total tests mismatch')
    require(collections.Counter(i['category'] for i in collected['items']) == collected['categories'], 'category totals')
    from tools.audit_cases import audit as audit_cases
    static = audit_cases(root)
    require(static == json.loads((ev / 'case-audit.json').read_text()) and static['status'] == 'PASS', 'static audit stale/failed')
    for item in static['cases']:
        require(not any('xfail' in d or 'skip' in d for d in item['decorators']), 'unhandled xfail/skip: ' + item['name'])
    old = (ev / 'audit-cases-at-final-run.py.txt').read_text()
    require(audit_logic(old) == audit_logic((root / 'tools/audit_cases.py').read_text()), 'audit metadata-only equivalence')
    pma = json.loads((root / 'manifest/pma-reset-reference.json').read_text())
    require(pma['kind'] == 'static-configuration-reference-not-live-DUT' and len(pma['entries']) == 32, 'PMA fixed oracle')
    hashed(root / pma['source'], pma['source_sha256'], 'PMA oracle source binding')
    isa = json.loads((ev / 'isa-sources.json').read_text())
    require(len(isa['sources']) == 3 and all(s['edition'] == 'v20260120' and s['raw_content_sha256'] is None
            for s in isa['sources']), 'ISA source edition/limitations')
    for source in isa['local_encoding']:
        hashed(source['path'], source['sha256'], 'Fence.scala encoding source')
    baseline = json.loads((root / 'manifest/baseline.json').read_text())
    require(baseline['soundness_review']['totals'] == index['totals'] and
            baseline['soundness_review']['status'] == 'regression-complete-with-open-scope', 'baseline current status')
    require(baseline['current_runs'] == {k: v['run'] for k, v in index['runs'].items()}, 'baseline run references')
    mutation = selftest()
    require(mutation['status'] == 'PASS', 'integrity predicate selftests')
    return failures, {'checks': checks, 'runs': details, 'predicate_selftest': mutation,
                      'limits': 'Integrity PASS is not ISA signoff or proof of semantic completeness.'}
