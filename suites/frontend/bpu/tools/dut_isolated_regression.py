"""Process-per-DUT orchestration using public pytest and Reactor APIs.

Reactor owns each domain's native merge/cleanup. A native build belongs to
exactly one child run, so aggregation never re-adds native counters. Functional
databases use Reactor's public, provenance-aware merge implementation.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Condition, Lock
import time
import traceback
from xml.etree import ElementTree as ET

from toffee import CoverageDatabase
from toffee.coverage_report import build_unified_coverage_model, parse_lcov, render_unified_coverage_html

from bpuverify.common.env.process_scope import SCOPES
from bpuverify.common.pytest.evidence import fingerprint, write_json, worst
from bpuverify.common.pytest.isolation import selected_ids
from bpuverify.common.pytest.points import make_report, summary_for, validate_report
from tools.refresh_coverage import ROOT, FLOOR, NAMES, digest, read, source_epoch, write
from tools.managed_regression import execution_verdicts, snapshot_publications


class WorkerBudget:
    """Acquire a whole worker allocation atomically; never reserve partial slots."""
    def __init__(self, slots):
        if type(slots) is not int or slots < 1:
            raise ValueError('worker budget must be positive')
        self.capacity = self.available = slots
        self.condition, self.stopped = Condition(), False

    def acquire(self, count):
        if type(count) is not int or not 1 <= count <= self.capacity:
            raise ValueError('invalid worker allocation')
        with self.condition:
            self.condition.wait_for(lambda: self.stopped or self.available >= count)
            if self.stopped:
                raise RuntimeError('isolated regression was stopped')
            self.available -= count

    def release(self, count):
        with self.condition:
            if self.available + count > self.capacity:
                raise ValueError('duplicate worker release')
            self.available += count
            self.condition.notify_all()

    def stop(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()


def worker_allocation(workers, cases, domains):
    """Use the requested budget when there is no other domain to share it."""
    if any(type(value) is not int or value<1 for value in (workers,cases,domains)):
        raise ValueError('positive worker, case and domain counts required')
    limit=workers if domains==1 else max(1,(workers+1)//2)
    return min(cases,limit)


def verify_child(directory, expected, domain, code):
    manifest = read(directory / 'manifest.json')
    if (manifest.get('format') != 'xreactor-execution' or manifest.get('state') != 'committed'
            or not manifest.get('coverage_complete') or not manifest.get('cleanup_complete')
            or manifest.get('cleanup_error') or code not in (0, 1) or manifest['pytest_exitstatus'] != code):
        raise ValueError(f'incomplete managed domain {domain}')
    for row in manifest['artifacts']:
        path = Path(row['path'])
        if not path.is_relative_to(directory) or fingerprint(path) != {key: row[key] for key in ('path', 'size', 'sha256')}:
            raise ValueError(f'changed managed artifact: {path}')
    tests = execution_verdicts(directory / 'pytest.xml', expected)
    if dict(Counter(tests.values())) != manifest['tests']:
        raise ValueError('domain verdicts differ from exact JUnit collection')
    native = read(directory / 'rtl-coverage-manifest.json')['native']
    if [row['dut'] for row in native] != ([] if domain == 'pure' else [domain]):
        raise ValueError(f'native coverage crossed DUT process boundary: {domain}')
    if domain == 'pure' and manifest['functional_groups']:
        raise ValueError('synthetic/model groups polluted the pure execution domain')
    receipts = [read(path) for path in (directory / 'processes').glob('*.json')]
    if not receipts or any(row['scope'] != domain for row in receipts):
        raise ValueError('missing or foreign process-scope receipt')
    observed = [row for row in receipts if row['snapshot']['packages']]
    if domain != 'pure' and not observed:
        raise ValueError('native scope never loaded its claimed DUT')
    for row in receipts:
        seen = row['snapshot']
        wanted = [] if not seen['packages'] else [domain]
        if seen['packages'] != wanted or seen['native_mappings'] != wanted:
            raise ValueError('foreign package or native library in a worker')
    return manifest, tests, native


def combine_features(plan, index, child_reports, tests):
    expected = {(feature, row['nodeid']) for row in index['cases'] for feature in row['features']}
    found, by_feature = set(), {point['id']: [] for point in plan['features']}
    definitions = {point['id']: point for point in plan['features']}
    for report in child_reports:
        validate_report(report)
        if report['integrity_errors']:
            raise ValueError('domain feature lifecycle is incomplete')
        for point in report['features']:
            if point['id'] not in by_feature:
                raise ValueError('unknown domain functional point')
            if {key: value for key, value in point.items() if key not in ('tests', 'status')} != definitions[point['id']]:
                raise ValueError('domain functional point definition changed')
            for row in point['tests']:
                key = point['id'], row['nodeid']
                if key in found or tests.get(row['nodeid']) != row['status']:
                    raise ValueError('duplicate or changed domain feature/test association')
                found.add(key)
                by_feature[point['id']].append(row)
    if found != expected:
        raise ValueError('functional point association differs from frozen collection')
    return make_report([dict(point, tests=by_feature[point['id']],
        status=worst({row['status'] for row in by_feature[point['id']]})) for point in plan['features']],
        integrity_errors=[], execution_owner='process-per-DUT')


def run(args):
    output = args.run_dir.resolve()
    epoch = source_epoch()
    extra = read(args.source_epoch) if args.source_epoch else {}
    if any(digest(path) != stamp for path, stamp in extra.items()):
        raise ValueError('supplied source epoch changed')
    protected = snapshot_publications(ROOT/'results')
    output.mkdir(parents=True, exist_ok=False)
    execution = output / 'execution'
    execution.mkdir()
    write(output / 'source-epoch.json', dict(epoch, **extra))
    result = dict(engine='xreactor-per-DUT', process_exitstatus=1, goal_complete=False,
                  reports_published=False, full_regression_complete=False, selected_regression_complete=False)
    started, children, child_lock = time.monotonic(), [], Lock()
    budget = WorkerBudget(args.workers)
    write(output / 'owner.json', dict(pid=os.getpid(), engine=result['engine'], worker_budget=args.workers,
        native_merge_owner='toffee', functional_merge_owner='toffee.CoverageDatabase',
        each_native_build_has_one_child_owner=True, cycle_traces=False, per_case_functional_exports=False,
        functional_transfer='one SDK-exported final database per nonempty domain; required for public merge'))
    try:
        index_path = output / 'partition-index.json'
        selection = list(args.select or ())
        command = [sys.executable, '-B', '-m', 'pytest', '-p', 'toffee._pytest',
                   '-q', '-p', 'no:cacheprovider', '--collect-only',
                   f'--regression-profile={args.regression_profile}', f'--bpu-write-partition={index_path}', *selection]
        with (output / 'collection.log').open('x') as stream:
            if subprocess.call(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT):
                raise ValueError('complete regression collection failed')
        index = read(index_path)
        scopes = {scope: selected_ids(index, scope) for scope in SCOPES}
        scopes = {scope: nodes for scope, nodes in scopes.items() if nodes}
        write(output / 'partition-summary.json', dict(total=index['count'],
            scopes={scope: len(nodes) for scope, nodes in scopes.items()},
            exact_disjoint_union=True, collection_sha256=index['collection_sha256']))
        index_sha256 = digest(index_path)

        def child(domain):
            nodes = scopes[domain]
            allocation = worker_allocation(args.workers,len(nodes),len(scopes))
            budget.acquire(allocation)
            try:
                import shutil
                if shutil.disk_usage(output).free < FLOOR:
                    raise RuntimeError('normal disk safety floor reached')
                directory = execution / 'domains' / domain
                directory.parent.mkdir(parents=True, exist_ok=True)
                env = os.environ.copy()
                env['BPUVERIFY_DUT_SCOPE'] = domain
                command = [sys.executable, '-B', '-m', 'toffee', 'run', '--output', str(directory),
                    '--workers', str(allocation), '--export-coverage-json', '-q', '-p', 'no:cacheprovider',
                    '--tb=short', f'--junitxml={directory}/pytest.xml', '--durations=20',
                    f'--regression-profile={args.regression_profile}', f'--bpu-dut-scope={domain}',
                    f'--bpu-partition-index={index_path}', f'--bpu-partition-sha256={index_sha256}', *selection]
                if allocation > 1:
                    command.append('--maxschedchunk=1')
                if getattr(args, 'keep_coverage_inputs', False) or getattr(args, 'dump_trace', False):
                    command.append('--keep-coverage-inputs')
                if getattr(args, 'dump_trace', False):
                    command.append('--dump-trace')
                before = time.monotonic()
                with (output / f'{domain}.log').open('x') as stream:
                    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream,
                                               stderr=subprocess.STDOUT, start_new_session=True)
                    with child_lock:
                        children.append(process)
                    write(output / f'{domain}-process.json', dict(pid=process.pid, command=command, workers=allocation))
                    print(f'{domain}: {len(nodes)} cases, {allocation} workers, PID {process.pid}', flush=True)
                    code = process.wait()
                manifest, tests, native = verify_child(directory, nodes, domain, code)
                write(output / f'{domain}-exit.json', dict(exitstatus=code, elapsed_seconds=time.monotonic() - before))
                return domain, directory, manifest, tests, native
            finally:
                budget.release(allocation)

        finished = []
        with ThreadPoolExecutor(max_workers=min(args.workers, len(scopes))) as pool:
            futures = [pool.submit(child, scope) for scope in sorted(scopes, key=lambda key: -len(scopes[key]))]
            try:
                for future in as_completed(futures):
                    finished.append(future.result())
            except BaseException:
                budget.stop()
                with child_lock:
                    for process in children:
                        if process.poll() is None and os.getpgid(process.pid) == process.pid:
                            os.killpg(process.pid, signal.SIGTERM)
                raise
        tests, native, database, feature_reports, artifacts, child_refs = {}, [], CoverageDatabase(), [], [], []
        junit = ET.Element('testsuites')
        for domain, directory, manifest, verdicts, rows in sorted(finished):
            if set(tests) & set(verdicts):
                raise ValueError('DUT partition executed a duplicate test')
            tests.update(verdicts)
            native.extend(rows)
            feature_reports.append(read(directory / 'feature-points.json'))
            for row in manifest['artifacts']:
                if row['kind'] == 'functional':
                    database.merge(CoverageDatabase.read_json(row['path']))
                artifacts.append(row)
            for suite in ET.parse(directory / 'pytest.xml').getroot():
                junit.append(suite)
            child_refs.append(dict(scope=domain, **fingerprint(directory / 'manifest.json')))
        expected = [row['nodeid'] for row in index['cases']]
        if set(tests) != set(expected) or len({row['dut'] for row in native}) != len(native):
            raise ValueError('partition union lost tests or duplicated a native build')
        ET.ElementTree(junit).write(output / 'pytest.xml', encoding='utf-8', xml_declaration=True)
        if execution_verdicts(output / 'pytest.xml', expected) != tests:
            raise ValueError('combined JUnit lost test identities')
        code = int(any(status in ('FAIL', 'ERROR', 'XPASS', 'SKIP') for status in tests.values()))
        functional = database.report() if database.groups else None
        if not selection and code == 0:
            from bpuverify.common.coverage.parallel import validate_parallel_case_coverage
            validate_parallel_case_coverage(functional, profile=args.regression_profile)
        features = combine_features(read(ROOT / 'verification_plan.json'), index, feature_reports, tests)
        if not selection and summary_for(features, 'all')['executed'] != len(features['features']):
            raise ValueError('complete regression has unexecuted functional points')
        write(execution / 'feature-points.json', features)
        write(execution / 'rtl-coverage-manifest.json', dict(format='bpu-managed-native-manifest', version=1,
              pytest_exitstatus=code, native=native, files=[row['path'] for row in native]))
        from bpuverify.common.coverage.rtl import build_report
        measured = build_report(execution / 'rtl-coverage-manifest.json', output / 'rtl-line-coverage.json')
        if not selection and set(measured['dut']) != set(NAMES):
            raise ValueError('complete regression did not measure all DUTs')
        groups = {row['instance']: row['coverage'] for row in functional['groups']} if functional else {}
        write(execution / 'functional-summary.json', dict(total_groups=len(groups),
              full_groups=sum(value == 100 for value in groups.values()), groups=groups,
              merge_owner='toffee.CoverageDatabase'))
        lines = [parse_lcov(Path(row['path']).with_suffix('.info'), name=row['dut']) for row in native]
        if functional or lines:
            render_unified_coverage_html(build_unified_coverage_model(functional=functional, line_coverage=lines,
                title=f'BPU isolated regression (test exit status {code})'), execution / 'coverage.html')
            artifacts.append(dict(kind='html', **fingerprint(execution / 'coverage.html')))
        if getattr(args, 'export_coverage_json', False) and functional:
            database.write_json(execution / 'functional-coverage.json')
            artifacts.append(dict(kind='functional', **fingerprint(execution / 'functional-coverage.json')))
        if source_epoch() != epoch or any(digest(path) != stamp for path, stamp in extra.items()):
            raise ValueError('execution source epoch changed')
        if any(digest(ROOT / 'results' / name) != stamp for name, stamp in protected.items()):
            raise ValueError('canonical reports changed')
        write_json(execution / 'manifest.json', dict(format='bpu-isolated-execution', version=1,
            state='committed', coverage_complete=True, cleanup_complete=True,
            pytest_exitstatus=code, tests=dict(Counter(tests.values())), functional_groups=len(groups),
            children=child_refs, artifacts=artifacts, native_merge_owner='toffee',
            functional_merge_owner='toffee.CoverageDatabase', partition_sha256=index_sha256))
        write(output / 'test-results.json', tests)
        write(output / 'feature-points.json', features)
        result.update(process_exitstatus=code, coverage_complete=True, exact_collection=len(expected),
            tests=dict(Counter(tests.values())), full_execution_complete=not selection,
            full_regression_complete=not selection and code == 0,
            selected_regression_complete=bool(selection) and code == 0,
            functional_points=summary_for(features), environment_contracts=summary_for(features, 'environment'),
            functional_groups=len(groups), full_groups=sum(value == 100 for value in groups.values()),
            native_source_lines={name: row['source_lines'] for name, row in measured['dut'].items()},
            source_epoch_unchanged=True, canonical_reports_unchanged=True,
            worker_inputs_reclaimed=all(not (directory / '_workers').exists() for _, directory, *_ in finished))
        write(output / 'summary.json', result)
    except BaseException as error:
        result.update(failure=repr(error), traceback=traceback.format_exc())
        write_json(execution / 'manifest.json', dict(format='bpu-isolated-execution', version=1,
            state='incomplete', error=repr(error), inputs_retained=True))
        print(result['traceback'], file=sys.stderr, flush=True)
    finally:
        result.update(elapsed_seconds=time.monotonic() - started, finished_at=datetime.now(timezone.utc).isoformat())
        write(output / 'exit.json', result)
    return result['process_exitstatus']
