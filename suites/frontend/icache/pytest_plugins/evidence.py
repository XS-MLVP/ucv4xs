"""Process-local simulation and controller-owned pytest verification evidence."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from datetime import timezone
from hashlib import file_digest
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from suites.frontend.icache.runtime.artifacts import case_directory
from suites.frontend.icache.runtime.artifacts import case_outputs
from suites.frontend.icache.runtime.dut import RTL_COVERAGE_FILES
from suites.frontend.icache.coverage.native import NativeCoverageRun
from suites.frontend.icache.coverage.native import reset_native_coverage_run
from suites.frontend.icache.coverage.native import set_native_coverage_run
from suites.frontend.icache.pytest_plugins.points import STATES, make_report


def status_of(report):
    if hasattr(report, 'wasxfail'):
        return 'XFAIL' if report.skipped else 'XPASS'
    if report.failed:
        if report.when == 'call' and str(report.longrepr).startswith('[XPASS(strict)]'):
            return 'XPASS'
        return 'FAIL' if report.when == 'call' else 'ERROR'
    if report.skipped:
        return 'SKIP'
    return 'PASS' if report.when == 'call' else None


def worst(statuses):
    return next((state for state in STATES if state in statuses), 'NOT_RUN')


def collection_digest(nodes):
    return sha256(json.dumps(nodes, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def fingerprint(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.resolve() != path:
        raise ValueError(f'artifact must be a regular non-symlink path: {path}')
    with path.open('rb') as stream:
        digest = file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), size=path.stat().st_size, sha256=digest)


def write_json(path, value):
    temporary = path.with_name('.' + path.name + '.pending')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


class Evidence:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.rootpath).resolve()
        self.worker = getattr(config, 'workerinput', {}).get('workerid')
        self.distributed = bool(self.worker or getattr(config.option, 'numprocesses', 0))
        self.run = Path(config.getoption('artifact_run')).resolve()
        if not self.run.is_relative_to(self.root / 'results') or self.run == self.root / 'results':
            raise pytest.UsageError('--artifact-run must be a new child directory under results/')
        self.plan = config._bpu_feature_plan
        self.feature_ids = config._bpu_feature_ids
        self.collected = None
        self.mapping, self.reports, self.receipts = {}, {}, {}
        self.started, self.collections, self.failed = set(), set(), set()
        self.errors = []
        self.native, self.native_token = None, None
        if not config.option.collectonly:
            if self.worker is None:
                self.run.mkdir(parents=True, exist_ok=False)
            if self.worker or not self.distributed:
                self.worker_root.mkdir(parents=True, exist_ok=False)
                if config.getoption('rtl_retention') == 'merged':
                    self.native = NativeCoverageRun(self.worker_root / 'native',
                        batch_size=config.getoption('rtl_batch_size'))
                self.native_token = set_native_coverage_run(self.native)

    @property
    def worker_root(self):
        return self.run / 'workers' / (self.worker or 'main')

    def pytest_collection_finish(self, session):
        # Record the final -k/-m selection, not a pre-deselection item list.
        items = session.items
        self.collected = [item.nodeid for item in items]
        for item in items:
            ids = set()
            for mark in item.iter_markers('feature'):
                if len(mark.args) != 1 or mark.args[0] not in self.feature_ids:
                    raise pytest.UsageError(f'{item.nodeid}: invalid feature marker {mark.args}')
                ids.add(mark.args[0])
            self.mapping[item.nodeid] = sorted(ids)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item):
        directory = case_directory(self.run, self.worker or 'main', item.nodeid)
        with case_outputs(directory):
            if self.native is not None:
                self.native.owner = item.nodeid
            try:
                yield
            finally:
                if self.native is not None:
                    self.native.end_test(item.nodeid, failed=item.nodeid in self.failed)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.failed:
            self.failed.add(report.nodeid)
        report.user_properties.extend((('bpu_features', self.mapping[item.nodeid]),
                                       ('bpu_worker', self.worker or 'main')))

    def pytest_runtest_logreport(self, report):
        if self.worker:
            return
        props = dict(report.user_properties)
        ids = props.get('bpu_features', [])
        if not set(ids) <= self.feature_ids:
            self.errors.append(f'unknown feature mapping: {report.nodeid}')
        known = self.mapping.setdefault(report.nodeid, ids)
        if known != ids:
            self.errors.append(f'feature mapping changed: {report.nodeid}')
        phases = self.reports.setdefault(report.nodeid, {})
        if report.when in phases:
            self.errors.append(f'duplicate report: {report.nodeid}/{report.when}')
        phases[report.when] = dict(status=status_of(report), outcome=report.outcome,
                                  worker=props.get('bpu_worker'))

    @pytest.hookimpl(optionalhook=True)
    def pytest_configure_node(self, node):
        worker = node.gateway.id
        if worker in self.started:
            self.errors.append(f'worker identity restarted: {worker}')
        self.started.add(worker)

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):
        worker = node.gateway.id
        if worker in self.collections:
            self.errors.append(f'duplicate worker collection: {worker}')
        self.collections.add(worker)
        if self.collected is None:
            self.collected = list(ids)
        elif list(ids) != self.collected:
            self.errors.append(f'collection differs: {worker}')

    def make_receipt(self, exitstatus):
        native = self.native.finish() if self.native is not None else dict(mode='raw')
        files = [dict(kind='rtl', **fingerprint(path)) for path in sorted(RTL_COVERAGE_FILES)]
        files.extend(dict(kind='functional', **fingerprint(path))
                     for path in sorted(self.worker_root.rglob('functional-coverage*.json')))
        nodes = self.collected or []
        return dict(worker=self.worker or 'main', pid=os.getpid(), pytest_exitstatus=int(exitstatus),
                    collected_count=len(nodes), collection_sha256=collection_digest(nodes),
                    files=files, native_retention=native, integrity_errors=list(self.errors))

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):
        worker = node.gateway.id
        if error is not None:
            self.errors.append(f'worker crashed: {worker}: {error}')
            return
        receipt = node.workeroutput.get('bpu_evidence')
        if receipt is None or receipt.get('worker') != worker or worker in self.receipts:
            self.errors.append(f'missing/wrong/duplicate worker receipt: {worker}')
        else:
            self.receipts[worker] = receipt
            self.errors.extend(receipt['integrity_errors'])
            # Exit 1 is pytest's ordinary FAIL/ERROR/strict-XPASS result, not
            # proof that the worker lost evidence. Explain it from the exact
            # worker-owned phase reports in validated_results. Other exits
            # remain infrastructure/integrity failures.
            if receipt['pytest_exitstatus'] not in (0, int(pytest.ExitCode.TESTS_FAILED)):
                self.errors.append(f'worker exitstatus: {worker}: {receipt["pytest_exitstatus"]}')

    def validated_results(self):
        if self.distributed and (not self.started or self.started != set(self.receipts)
                                 or self.started != self.collections):
            self.errors.append('not every started worker collected and finished')
        expected = set(self.collected or ())
        if not expected or len(expected) != len(self.collected or ()) or set(self.reports) != expected:
            self.errors.append('reported tests do not exactly match unique collection')
        tests, files, paths = [], [], set()
        for nodeid in sorted(expected | set(self.reports)):
            phases = self.reports.get(nodeid, {})
            if not {'setup', 'teardown'} <= phases.keys():
                self.errors.append(f'incomplete lifecycle: {nodeid}')
            if phases.get('setup', {}).get('outcome') == 'passed' and 'call' not in phases:
                self.errors.append(f'missing call report: {nodeid}')
            owners = {row['worker'] for row in phases.values()}
            if len(owners) != 1 or not owners <= set(self.receipts):
                self.errors.append(f'invalid lifecycle worker: {nodeid}')
            tests.append(dict(nodeid=nodeid, status=worst({row['status'] for row in phases.values()}), phases=phases))
        for worker, receipt in sorted(self.receipts.items()):
            if receipt['pytest_exitstatus'] == int(pytest.ExitCode.TESTS_FAILED):
                explained = any(row['status'] in ('FAIL', 'ERROR', 'XPASS')
                    and {phase['worker'] for phase in row['phases'].values()} == {worker}
                    for row in tests)
                if not explained:
                    self.errors.append(f'unexplained worker tests-failed exit: {worker}')
            if (receipt['collected_count'] != len(self.collected or ()) or
                    receipt['collection_sha256'] != collection_digest(self.collected or [])):
                self.errors.append(f'receipt collection differs: {worker}')
            for entry in receipt['files']:
                path = Path(entry['path'])
                try:
                    valid = (entry['kind'] in ('rtl', 'functional') and path not in paths
                             and path.is_relative_to(self.run / 'workers' / worker)
                             and fingerprint(path) == {key: entry[key] for key in ('path', 'size', 'sha256')})
                except (OSError, ValueError):
                    valid = False
                if not valid:
                    self.errors.append(f'invalid artifact: {path}')
                paths.add(path)
                files.append(dict(worker=worker, **entry))
        return tests, files

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.config.option.collectonly:
            return
        if self.worker or not self.distributed:
            receipt = self.make_receipt(exitstatus)
            write_json(self.worker_root / 'receipt.json', receipt)
            if self.worker:
                self.config.workeroutput['bpu_evidence'] = receipt
                return
            self.receipts['main'] = receipt
        tests, files = self.validated_results()
        features = []
        for planned in self.plan:
            cases = [row for row in tests if planned['id'] in self.mapping.get(row['nodeid'], [])]
            features.append(dict(planned, status=worst({row['status'] for row in cases}),
                tests=[dict(nodeid=row['nodeid'], status=row['status']) for row in cases]))
        if (self.errors or any(row['status'] in ('ERROR', 'FAIL', 'XPASS') for row in tests)) and not session.exitstatus:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        now = datetime.now(timezone.utc).isoformat()
        evidence = dict(format='bpu-pytest-evidence', version=1, generated_at=now,
            pytest_exitstatus=int(session.exitstatus), integrity_errors=self.errors,
            evidence_complete=not self.errors, collected_count=len(self.collected or []),
            test_status_counts=dict(Counter(row['status'] for row in tests)), tests=tests,
            workers=[dict(worker=worker, receipt=str(self.run / 'workers' / worker / 'receipt.json'),
                          **fingerprint(self.run / 'workers' / worker / 'receipt.json'))
                     for worker in sorted(self.receipts)])
        write_json(self.run / 'evidence.json', evidence)
        write_json(self.run / 'feature-points.json', make_report(features, generated_at=now))
        inputs = Counter()
        for receipt in self.receipts.values():
            inputs.update(receipt['native_retention'].get('input_files_by_dut', {}))
        write_json(self.run / 'rtl-coverage-manifest.json', dict(format='bpu-rtl-coverage-manifest',
            version=1, generated_at=now, pytest_exitstatus=int(session.exitstatus),
            files=[str(Path(row['path']).relative_to(self.root)) for row in files if row['kind'] == 'rtl'],
            native_retention=dict(mode=self.config.getoption('rtl_retention'),
                                  input_files=sum(inputs.values()), input_files_by_dut=dict(inputs))))
        write_json(self.run / 'functional-manifest.json', dict(format='bpu-functional-manifest',
            version=1, pytest_exitstatus=int(session.exitstatus),
            files=[row for row in files if row['kind'] == 'functional']))

    def pytest_unconfigure(self):
        if self.native_token is not None:
            reset_native_coverage_run(self.native_token)
            self.native_token = None
