"""Run frozen production through toffee; keep the legacy publisher for replay.

Native raw retention is bounded by the production pytest plugin. Functional
inputs must have been written during this invocation, not merely exist in a
historical directory. JSON here records run results, never per-cycle traces.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from datetime import timezone
from hashlib import file_digest
import json
from importlib.util import find_spec
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
from suites.frontend.bpu.pytest_plugins.regression import PROFILES
from suites.frontend.bpu.pytest_plugins.points import summary_for, validate_report
NAMES = ('abtb','bpu','ittage','mbtb','ras','sc','tage','ubtb','uras','utage')
FLOOR = 86436216832
DEFAULT_WORKERS = min(32, len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity')
                      else (os.cpu_count() or 1))


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def source_epoch():
    """Freeze source, DUTs, and the actual Python execution dependencies."""
    paths = {ROOT / name for name in ('pytest.ini', 'requirements.txt', 'verification_plan.json')}
    lock = ROOT / 'dependencies/versions.json'
    if lock.is_file():
        paths.add(lock)
    from ucv.runtime import suite_python_sources
    paths.update(suite_python_sources(ROOT))
    for directory in ('rtl', 'dut'):
        paths.update(path for path in (ROOT / directory).rglob('*') if path.is_file()
                     and (path.suffix in ('.py', '.so', '.v', '.sv', '.yaml', '.json')
                          or '.so.' in path.name or path.name == 'Makefile'))
    for name in ('toffee', 'xspcomm', 'pytest', '_pytest', 'pytest_asyncio', 'xdist', 'execnet'):
        spec = find_spec(name)
        if spec is None:
            raise RuntimeError(f'missing production dependency: {name}')
        if spec.origin and spec.origin not in ('built-in', 'frozen'):
            paths.add(Path(spec.origin))
        for directory in spec.submodule_search_locations or ():
            paths.update(path for path in Path(directory).rglob('*')
                         if path.is_file() and (path.suffix in ('.py', '.so')
                                                or '.so.' in path.name))
    return {str(path.resolve()): digest(path) for path in sorted(paths)}


def pytest_command(output, workers, profile='production'):
    if workers < 1:
        raise ValueError('workers must be positive; use 1 for serial execution')
    if profile not in PROFILES:
        raise ValueError(f'unknown regression profile: {profile}')
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
               '--rtl-retention=merged', f'--artifact-run={output}/pytest-artifacts',
               f'--junitxml={output}/pytest.xml', '--durations=20', f'--regression-profile={profile}']
    if workers > 1:
        # Default xdist chunks can pin hundreds of multi-minute scenarios to
        # one worker. Keep only its required current/next lookahead instead.
        command.extend(('-n', str(workers), '--dist=load', '--maxschedchunk=1',
                        '--max-worker-restart=0'))
    return command


def execution_inputs(run, expected, verdicts, *, require_coverage=True):
    """Revalidate current worker receipts; never discover inputs in old results."""
    from suites.frontend.bpu.pytest_plugins.evidence import collection_digest
    from suites.frontend.bpu.pytest_plugins.evidence import fingerprint
    evidence = read(run / 'evidence.json')
    if (evidence.get('format') != 'bpu-pytest-evidence' or evidence.get('version') != 1
            or evidence.get('pytest_exitstatus') != 0 or evidence.get('integrity_errors')
            or evidence.get('evidence_complete') is not True
            or evidence.get('collected_count') != len(expected)):
        raise ValueError('incomplete or failed controller evidence')
    rows = evidence['tests']
    if (len(rows) != len(expected) or {row['nodeid']: row['status'] for row in rows} != verdicts
            or evidence['test_status_counts'] != dict(Counter(verdicts.values()))):
        raise ValueError('controller results differ from complete collection/JUnit')
    files, owners, seen = [], set(), set()
    native_inputs = Counter()
    for worker in evidence['workers']:
        owner = worker['worker']
        receipt_path = run / 'workers' / owner / 'receipt.json'
        if (owner in owners or owner != 'main' and not (owner.startswith('gw') and owner[2:].isdigit())
                or worker['receipt'] != str(receipt_path)
                or fingerprint(receipt_path) != {key: worker[key] for key in ('path', 'size', 'sha256')}):
            raise ValueError('invalid worker receipt identity')
        owners.add(owner)
        receipt = read(receipt_path)
        if (receipt['worker'] != owner or receipt['pytest_exitstatus'] != 0
                or receipt['integrity_errors'] or receipt['collected_count'] != len(expected)
                or receipt['collection_sha256'] != collection_digest(expected)):
            raise ValueError('incomplete or failed worker receipt')
        native_inputs.update(receipt['native_retention'].get('input_files_by_dut', {}))
        for entry in receipt['files']:
            path = Path(entry['path'])
            if (entry['kind'] not in ('rtl', 'functional') or path in seen
                    or not path.is_relative_to(receipt_path.parent)
                    or fingerprint(path) != {key: entry[key] for key in ('path', 'size', 'sha256')}):
                raise ValueError('invalid current-run artifact: ' + str(path))
            seen.add(path)
            files.append(dict(worker=owner, **entry))
    if not owners:
        raise ValueError('no completed worker receipts')
    for row in rows:
        phases = row['phases']
        if (set(phases) != {'setup', 'call', 'teardown'}
                or len({phase['worker'] for phase in phases.values()}) != 1
                or not {phase['worker'] for phase in phases.values()} <= owners):
            raise ValueError('incomplete test lifecycle: ' + row['nodeid'])
    functional = read(run / 'functional-manifest.json')
    rtl = read(run / 'rtl-coverage-manifest.json')
    actual_functional = [entry for entry in files if entry['kind'] == 'functional']
    actual_rtl = sorted(str(Path(entry['path']).relative_to(ROOT)) for entry in files if entry['kind'] == 'rtl')
    if (functional.get('format') != 'bpu-functional-manifest' or functional.get('version') != 1
            or functional.get('pytest_exitstatus') != 0
            or sorted(functional['files'], key=lambda entry: entry['path']) != sorted(actual_functional, key=lambda entry: entry['path'])
            or rtl.get('format') != 'bpu-rtl-coverage-manifest' or rtl.get('version') != 1
            or rtl.get('pytest_exitstatus') != 0 or sorted(rtl['files']) != actual_rtl
            or rtl['native_retention'].get('mode') != 'merged'
            or rtl['native_retention'].get('input_files_by_dut') != dict(native_inputs)
            or rtl['native_retention'].get('input_files') != sum(native_inputs.values())):
        raise ValueError('current manifests differ from validated worker receipts')
    paths = [Path(entry['path']) for entry in actual_functional]
    if require_coverage and (not paths or not actual_rtl):
        raise ValueError('no current-run functional/native coverage')
    return sorted(paths)


def lcov(path):
    source, result = None, {}
    for line in Path(path).read_text().splitlines():
        if line.startswith('SF:'):
            source = line[3:]
        elif line.startswith('DA:'):
            number, count = map(int, line[3:].split(','))
            key = (source, number)
            if source is None or key in result or count < 0:
                raise ValueError(f'invalid/duplicate native LCOV line: {path}:{line}')
            result[key] = count
        elif line == 'end_of_record':
            source = None
    if not result:
        raise ValueError(f'empty native LCOV: {path}')
    return result


def junit_verdicts(path, expected):
    # Parameter text can itself contain '::' or XML control characters.
    # Encode expected identities exactly as pytest does; never guess by
    # decoding or normalizing arbitrary executed names.
    from _pytest.junitxml import bin_xml_escape
    from _pytest.junitxml import mangle_test_address
    keys = {}
    for node in expected:
        parts = mangle_test_address(node)
        key = ('.'.join(parts[:-1]), bin_xml_escape(parts[-1]))
        if key in keys:
            raise ValueError(f'ambiguous JUnit identity: {node}')
        keys[key] = node
    actual = {}
    for case in ET.parse(path).getroot().findall('.//testcase'):
        key = (case.get('classname'), case.get('name'))
        if key not in keys or keys[key] in actual:
            raise ValueError(f'unexpected/duplicate executed test: {key}')
        if case.find('failure') is not None or case.find('error') is not None:
            raise ValueError(f'failed test: {keys[key]}')
        skipped = case.find('skipped')
        if skipped is not None and skipped.get('type') != 'pytest.xfail':
            raise ValueError(f'unexpected skipped test: {keys[key]}')
        actual[keys[key]] = 'XFAIL' if skipped is not None else 'PASS'
    if set(actual) != set(expected):
        raise ValueError('executed JUnit cases do not equal complete collection')
    return actual


def validate_functional_points(report, plan, previous, verdicts):
    """Accept complete current-plan growth, never missing or retired points."""
    def identities(rows, label):
        ids = [row.get('id') for row in rows]
        if (not ids or any(not isinstance(value, str) or not value for value in ids)
                or len(ids) != len(set(ids))):
            raise ValueError(f'invalid or duplicate {label} functional point IDs')
        return set(ids)

    required = identities(plan['features'], 'planned')
    prior = identities(previous['features'], 'previous')
    actual = identities(report['features'], 'reported')
    if not prior <= required:
        raise ValueError('current plan removes previously published functional points')
    if actual != required:
        raise ValueError(f'current functional point identities differ: missing={sorted(required-actual)}, extra={sorted(actual-required)}')
    statuses = Counter()
    for row in report['features']:
        cases = row.get('tests', [])
        nodes = [case.get('nodeid') for case in cases]
        if (not nodes or len(nodes) != len(set(nodes))
                or any(case.get('status') not in ('PASS', 'XFAIL')
                       or verdicts.get(case.get('nodeid')) != case.get('status') for case in cases)):
            raise ValueError('incomplete or invalid executed functional point: ' + row['id'])
        expected = 'PASS' if any(case['status'] == 'PASS' for case in cases) else 'XFAIL'
        if row.get('status') != expected:
            raise ValueError('functional point verdict differs from executed cases: ' + row['id'])
        statuses[expected] += 1
    validate_report(report)
    summary = summary_for(report, 'all')
    reported_counts = summary.get('status_counts', {})
    if (any(type(count) is not int or count < 0 for count in reported_counts.values())
            or {state: count for state, count in reported_counts.items() if count} != dict(statuses)
            or type(summary.get('planned')) is not int or summary['planned'] != len(required)
            or type(summary.get('executed')) is not int or summary['executed'] != len(required)
            or type(summary.get('passed')) is not int or summary['passed'] != statuses['PASS']):
        raise ValueError('functional point summary differs from the complete current plan')


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, default=ROOT / 'results' /
                        ('regression-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]))
    parser.add_argument('--engine', choices=('managed','legacy'), default='managed',
                        help='Production uses toffee run; legacy is for historical reproduction only')
    parser.add_argument('--keep-coverage-inputs', action='store_true',
                        help='Managed debug only: retain original worker inputs')
    parser.add_argument('--export-coverage-json', action='store_true',
                        help='Managed debug only: retain one final functional database')
    parser.add_argument('--dump-trace', action='store_true',
                        help='Managed debug only: export cycle traces and retain worker inputs')
    parser.add_argument('--source-epoch', type=Path, help='Optional additional source hash ledger')
    parser.add_argument('--regression-profile', choices=PROFILES, default='production',
                        help='Default production uses representative ABTB coordinates; physical is an opt-in deep regression')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS,
                        help=f'Independent pytest processes (default: {DEFAULT_WORKERS}, capped by CPU affinity); 1 runs serially')
    parser.add_argument('--select', nargs='+', metavar='TEST',
                        help='Run selected tests/ paths or nodeids with the same isolation; never replace full-suite reports')
    args = parser.parse_args(argv)
    if args.engine == 'legacy' and (args.keep_coverage_inputs or args.export_coverage_json or args.dump_trace):
        parser.error('managed debug flags cannot be used with --engine=legacy')
    if args.workers < 1:
        parser.error('--workers must be positive; use 1 for serial execution')
    for scope in args.select or ():
        path = (ROOT / scope.split('::', 1)[0]).resolve()
        if not path.is_relative_to(ROOT / 'tests') or not path.exists():
            parser.error('--select requires existing repository tests/ paths or nodeids')
    output = args.run_dir.resolve()
    if not output.is_relative_to(ROOT / 'results') or output == ROOT / 'results':
        parser.error('--run-dir must be a new directory under repository results/')
    if args.engine == 'managed':
        from tools.managed_regression import run
        return run(args)
    automatic_epoch = source_epoch()
    epoch = dict(automatic_epoch)
    if args.source_epoch:
        supplied = read(args.source_epoch)
        if not all(digest(path) == sha for path, sha in supplied.items()):
            raise ValueError('supplied source epoch changed before full regression')
        epoch.update(supplied)
    output.mkdir(parents=True, exist_ok=False)
    def verify_source():
        return source_epoch() == automatic_epoch and all(digest(path) == sha for path, sha in epoch.items())
    if not verify_source():
        raise ValueError('source epoch changed before full regression')
    baseline = read(ROOT / 'results/rtl-line-coverage.json')
    from tools.regression_profiles import load_baseline, compare_native, publish_index, retain_legacy_baseline
    scoped_baseline = load_baseline(ROOT, args.regression_profile, read=read, digest=digest)
    # The published pre-profile full physical regression remains a strict
    # native baseline for the first deep run, but not for representatives.
    if scoped_baseline is None and args.regression_profile == 'physical':
        published_summary = read(ROOT/'results/summary.json')
        if published_summary.get('regression_profile') not in (None, 'physical'):
            raise ValueError('deep regression needs the retained physical baseline, not a production baseline')
        scoped_baseline = baseline
    previous_features = read(ROOT / 'results/feature-points.json')
    expected_xfails = {case['nodeid'] for row in previous_features['features']
                       for case in row['tests'] if case['status'] == 'XFAIL'}
    protected = {name: digest(ROOT/'results'/name) for name in (
        'feature-points.json','rtl-coverage-manifest.json','rtl-line-coverage.json',
        'verification-report.html','summary.json')}
    write(output/'source-epoch.json', epoch)
    write(output/'owner.json', dict(pid=os.getpid(), started_at=datetime.now(timezone.utc).isoformat(),
        source_files=len(epoch), source_ledger_sha256=digest(output/'source-epoch.json'),
        workers=args.workers, worker_restart=False, artifact_isolation='run/worker/full-nodeid-sha256',
        regression_profile=args.regression_profile,
        selected_scopes=args.select, full_suite_requested=not bool(args.select),
        normal_disk_floor_bytes=FLOOR, cycle_trace_export=False, native_retention='merged',
        independent_full_dynamic_audit_complete=False, goal_complete=False))
    stages = []

    def command(label, arguments):
        if shutil.disk_usage(output).free < FLOOR:
            raise RuntimeError('normal disk safety floor reached')
        log = output/f'{label}.log'
        stage_started = time.monotonic()
        with log.open('x') as stream:
            child = subprocess.Popen(arguments, cwd=ROOT, env=os.environ.copy(),
                                     stdout=stream, stderr=subprocess.STDOUT)
            write(output/f'{label}-process.json', dict(pid=child.pid, owner_pid=os.getpid(), command=arguments))
            print(f'{label}: PID {child.pid}, {log}', flush=True)
            code = child.wait()
        stages.append(dict(stage=label, exitstatus=code, log=str(log), sha256=digest(log),
                           elapsed_seconds=time.monotonic() - stage_started))
        if code:
            raise RuntimeError(f'{label} exited with {code}; see {log}')

    result = dict(process_exitstatus=1, goal_complete=False, full_regression_complete=False,
                  regression_profile=args.regression_profile)
    try:
        common = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                  f'--regression-profile={args.regression_profile}']
        command('collection', common+['--collect-only', *(args.select or ())])
        expected = [line for line in (output/'collection.log').read_text().splitlines()
                    if line.startswith('tests/') and '::' in line]
        if not expected or len(expected) != len(set(expected)):
            raise ValueError('invalid full collection')
        label = 'selected regression' if args.select else 'full regression'
        print(f'{label}: {len(expected)} tests, {args.workers} worker(s), {output}', flush=True)
        command('pytest', pytest_command(output, args.workers, args.regression_profile) + (args.select or []))
        if not verify_source():
            raise ValueError('source epoch changed during full regression')
        tests = junit_verdicts(output/'pytest.xml', expected)
        required_xfails = expected_xfails & set(expected) if args.select else expected_xfails
        if {node for node, verdict in tests.items() if verdict == 'XFAIL'} != required_xfails:
            raise ValueError('known strict XFAIL set changed')
        artifact_run = output / 'pytest-artifacts'
        functional_paths = (execution_inputs(artifact_run, expected, tests, require_coverage=False)
                            if args.select else execution_inputs(artifact_run, expected, tests))
        for name in ('feature-points.json', 'rtl-coverage-manifest.json', 'functional-manifest.json'):
            shutil.copyfile(artifact_run / name, output / name)
        from suites.frontend.bpu.coverage.rtl import build_report
        from toffee.coverage_report import load_functional_coverage
        from toffee.coverage_report import generate_unified_coverage_report
        native = build_report(output/'rtl-coverage-manifest.json', output/'rtl-line-coverage.json')
        native.update(regression_profile=args.regression_profile, selected_measurement=bool(args.select))
        with (output/'rtl-line-coverage.json').open('w') as stream:
            json.dump(native, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        if args.select:
            # A selected run is qualified for its own complete collection only.
            # Missing modules/feature bins are not waived in the full workflow;
            # no canonical report or historical coverage is changed here.
            functional = load_functional_coverage(functional_paths)
            write(output/'functional-coverage.json', functional)
            if functional or native['dut']:
                generate_unified_coverage_report(functional_paths=[output/'functional-coverage.json'] if functional else [],
                    line_coverage=[(name, row['lcov_file']) for name, row in sorted(native['dut'].items())],
                    output=output/'verification-report.html', title='Kunminghu-v3 selected regression (not full-suite acceptance)')
            if not verify_source() or any(digest(ROOT/'results'/name) != sha for name, sha in protected.items()):
                raise ValueError('source or published reports changed during selected regression')
            result.update(process_exitstatus=0, selected_regression_complete=True,
                full_regression_complete=False, reports_published=False,
                tests=dict(Counter(tests.values())), exact_selected_collection=len(expected),
                selected_scopes=args.select, workers=args.workers,
                coverage_report=str(output/'verification-report.html') if functional or native['dut'] else None,
                functional_points=summary_for(read(output/'feature-points.json')),
                environment_contracts=summary_for(read(output/'feature-points.json'),'environment'),
                all_points=summary_for(read(output/'feature-points.json'),'all'),
                functional_groups=len(functional['groups']) if functional else 0,
                native_source_lines={name: row['source_lines'] for name, row in native['dut'].items()},
                artifact_evidence=str(artifact_run/'evidence.json'))
            write(output/'test-results.json', tests)
            write(output/'summary.json', result)
            return 0
        if set(native['dut']) != set(NAMES):
            raise ValueError('full regression did not cover all ten native DUTs')
        losses, comparison = compare_native(native, baseline, scoped_baseline, lcov=lcov)
        comparison.update(regression_profile=args.regression_profile,
                          published_scope=read(ROOT/'results/summary.json').get('regression_profile', 'legacy-exhaustive'))
        write(output/'native-scope-comparison.json', comparison)
        if losses:
            write(output/'lost-baseline-lines.json', losses)
            raise ValueError('full regression lost previously covered source lines')
        functional = load_functional_coverage(functional_paths)
        from suites.frontend.bpu.coverage.parallel import validate_parallel_case_coverage
        matrices = validate_parallel_case_coverage(functional, profile=args.regression_profile)
        write(output/'matrix-acceptance.json', matrices)
        write(output/'functional-coverage.json', functional)
        generate_unified_coverage_report(functional_paths=[output/'functional-coverage.json'],
            line_coverage=[(name,row['lcov_file']) for name,row in sorted(native['dut'].items())],
            output=output/'verification-report.html', title=f'Kunminghu-v3 {args.regression_profile} regression (physical denominator retained)')
        features = read(output/'feature-points.json')
        validate_functional_points(features, read(ROOT/'verification_plan.json'), previous_features, tests)
        result.update(process_exitstatus=0, full_regression_complete=True,
            tests=dict(Counter(tests.values())), exact_full_collection=len(expected),
            functional_points=summary_for(features), environment_contracts=summary_for(features,'environment'),
            all_points=summary_for(features,'all'), functional_groups=len(functional['groups']),
            functional_fully_covered=sum(group['coverage'] >= 100 for group in functional['groups']),
            native_source_lines={name:row['source_lines'] for name,row in native['dut'].items()},
            baseline_native_hit_losses=0 if scoped_baseline is not None else None, all10_native_DUTs=True,
            native_scope_comparison=comparison, matrix_acceptance=matrices,
            workers=args.workers, artifact_evidence=str(artifact_run / 'evidence.json'),
            independent_full_dynamic_audit_complete=False, formal_current=False)
        write(output/'test-results.json', tests)
        write(output/'summary.json', result)
        if not verify_source() or any(digest(ROOT/'results'/name) != sha for name,sha in protected.items()):
            raise ValueError('source or published reports changed before publication')
        from tools.sync_published_lcov import sync
        sync(output / 'rtl-line-coverage.json', root=ROOT)  # Validate all LCOV before publication.
        # Preserve the previous scope's published view before changing the
        # default. Native payloads still reference their original run files.
        archive = ROOT/'results/regression-profiles' / ('previous-published-' + uuid4().hex[:8])
        archive.mkdir(parents=True, exist_ok=False)
        for name in protected:
            shutil.copyfile(ROOT/'results'/name, archive/name)
        retain_legacy_baseline(ROOT, archive, read(archive/'summary.json'), digest=digest)
        # Only completed, scope-checked measurements replace current reports.
        # They still do not claim the remaining physical/dynamic goal is done.
        for name in ('feature-points.json','rtl-coverage-manifest.json','rtl-line-coverage.json',
                     'verification-report.html','summary.json'):
            target = ROOT/'results'/name
            temporary = target.with_suffix(target.suffix+'.refresh-pending')
            with (output/name).open('rb') as source, temporary.open('xb') as stream:
                shutil.copyfileobj(source, stream)
            temporary.replace(target)
        write(output / 'published-lcov-sync.json', sync(ROOT / 'results/rtl-line-coverage.json', root=ROOT, publish=True))
        result['reports_published'] = True
    except BaseException as error:
        result.update(process_exitstatus=1, failure=repr(error), traceback=traceback.format_exc())
        print(result['traceback'], file=sys.stderr, flush=True)
    finally:
        result.update(stages=stages, elapsed_seconds=time.monotonic() - started,
                      finished_at=datetime.now(timezone.utc).isoformat())
        write(output/'exit.json', result)
        if result.get('reports_published'):
            publish_index(ROOT, args.regression_profile, output, digest=digest)
    return result['process_exitstatus']


if __name__ == '__main__':
    raise SystemExit(main())
