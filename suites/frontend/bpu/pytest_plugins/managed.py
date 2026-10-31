"""BPU domain evidence only: toffee owns capture, merge and input cleanup."""
from hashlib import sha256
from pathlib import Path

import pytest

from suites.frontend.bpu.runtime.artifacts import case_outputs
from suites.frontend.bpu.coverage.exports import set_functional_exports, reset_functional_exports
from suites.frontend.bpu.pytest_plugins.evidence import status_of, worst, write_json
from suites.frontend.bpu.pytest_plugins.points import make_report


def measured_functional_case(nodeid):
    """Only hardware scenarios contribute; model/schema tests are not coverage."""
    parts = Path(nodeid.split('::', 1)[0]).parts
    return len(parts) >= 4 and parts[0] == 'tests' and parts[2] == 'testcase'


class ManagedFeatures:
    def __init__(self, config, output):
        self.config, self.output = config, Path(output).resolve()
        self.worker = getattr(config, 'workerinput', {}).get('workerid', 'main')
        self.mapping, self.phases = {}, {}
        self.token = set_functional_exports(False)

    def pytest_collection_modifyitems(self, items):
        for item in items:
            ids = set()
            for marker in item.iter_markers('feature'):
                if len(marker.args) != 1 or marker.args[0] not in self.config._bpu_feature_ids:
                    raise pytest.UsageError(f'{item.nodeid}: invalid functional point')
                ids.add(marker.args[0])
            self.mapping[item.nodeid] = sorted(ids)
            if not measured_functional_case(item.nodeid):
                item.add_marker(pytest.mark.toffee_functional_coverage(False))

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item):
        directory = (self.output/'_workers'/self.worker/'project'/
                     sha256(item.nodeid.encode()).hexdigest()/'results')
        # The harness owns this per-case directory: create it before the case so
        # that an explicit results write cannot fail with FileNotFoundError and
        # turn an expected defect verdict into a spurious harness failure.
        directory.mkdir(parents=True, exist_ok=True)
        # Pure tests may deliberately exercise JSON serialization in tmp_path.
        # Their groups are excluded by the public functional-capture marker.
        token = set_functional_exports(not measured_functional_case(item.nodeid))
        try:
            with case_outputs(directory):
                yield
        finally:
            reset_functional_exports(token)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        outcome.get_result().user_properties.extend((
            ('bpu_features', self.mapping[item.nodeid]), ('bpu_worker', self.worker)))

    def pytest_runtest_logreport(self, report):
        if self.worker != 'main':
            return
        properties = dict(report.user_properties)
        ids = properties.get('bpu_features', [])
        if not set(ids) <= self.config._bpu_feature_ids:
            raise ValueError('unknown worker feature identity')
        previous = self.mapping.setdefault(report.nodeid, ids)
        if previous != ids:
            raise ValueError('worker functional point association changed')
        phases = self.phases.setdefault(report.nodeid, {})
        if report.when in phases:
            raise ValueError('duplicate pytest lifecycle report')
        phases[report.when] = dict(status=status_of(report), outcome=report.outcome,
                                   worker=properties.get('bpu_worker'))

    @pytest.hookimpl(optionalhook=True)
    def pytest_toffee_coverage(self, config, functional, native, pytest_exitstatus):
        if any(set(phases) != ({'setup','call','teardown'} if phases.get('setup',{}).get('outcome') == 'passed' else {'setup','teardown'}) or
               len({p['worker'] for p in phases.values()}) != 1 for phases in self.phases.values()):
            raise ValueError('incomplete or mixed-owner project lifecycle')
        if config.getoption('bpu_full_suite') and pytest_exitstatus == 0:
            from suites.frontend.bpu.coverage.parallel import validate_parallel_case_coverage
            validate_parallel_case_coverage(functional, profile=config.getoption('regression_profile'))
        groups = {row['instance']: row['coverage'] for row in functional['groups']} if functional else {}
        if functional and len(groups) != len(functional['groups']):
            raise ValueError('duplicate merged functional group identity')
        write_json(self.output/'functional-summary.json', dict(
            format='bpu-managed-functional-summary', pytest_exitstatus=pytest_exitstatus,
            merge_owner='toffee', merge_count=1, total_groups=len(groups),
            full_groups=sum(value == 100 for value in groups.values()), groups=groups))
        rows = []
        root = Path(config.rootpath).resolve()
        for row in native:
            packages = {Path(path).parent.resolve() for path in row['build']['files']
                        if Path(path).name == '__init__.py'}
            modules = {entry.name for entry in (root/'dut').iterdir()
                       if entry.is_dir() and entry.resolve() in packages}
            if len(modules) != 1:
                raise ValueError('native build does not identify one canonical DUT')
            rows.append(dict(row, dut=modules.pop()))
        if len({row['dut'] for row in rows}) != len(rows):
            raise ValueError('multiple builds of one DUT cannot form one BPU baseline')
        write_json(self.output/'rtl-coverage-manifest.json', dict(
            format='bpu-managed-native-manifest', version=1, pytest_exitstatus=pytest_exitstatus,
            native=rows, files=[row['path'] for row in rows]))

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        if self.worker != 'main':
            return
        by_feature = {feature['id']: [] for feature in self.config._bpu_feature_plan}
        errors = []
        for node, phases in self.phases.items():
            if set(phases) != ({'setup', 'call', 'teardown'} if phases.get('setup', {}).get('outcome') == 'passed' else {'setup', 'teardown'}) or len({p['worker'] for p in phases.values()}) != 1:
                errors.append(f'incomplete or mixed-owner lifecycle: {node}')
            status = worst({p['status'] for p in phases.values() if p['status'] is not None})
            for feature in self.mapping[node]:
                by_feature[feature].append(dict(nodeid=node, status=status))
        features = [dict(feature, tests=by_feature[feature['id']],
                         status=worst({row['status'] for row in by_feature[feature['id']]}))
                    for feature in self.config._bpu_feature_plan]
        self.point_report = make_report(features, integrity_errors=errors)
        write_json(self.output/'feature-points.json', self.point_report)
        if errors:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_unconfigure(self):
        reset_functional_exports(self.token)

    def pytest_terminal_summary(self, terminalreporter):
        if self.worker != 'main' or not hasattr(self, 'point_report'):
            return
        for name in ('hardware', 'environment'):
            row = self.point_report['summaries'][name]
            terminalreporter.write_line(
                f"{name} verification points: {row['passed']}/{row['planned']} PASS; "
                f"{row['executed']} executed; {row['status_counts']}")
