"""Project-owned pytest evidence grouped by collected ICache feature markers."""

from __future__ import annotations

import json
from uuid import uuid4
from collections import defaultdict
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any

import pytest
from toffee.outcomes import case_status, phase_record

from suites.frontend.icache.testbenches.shared.env.pytest_plugins.scheduling import order_tests
from suites.frontend.icache.testbenches.shared.env.dut import RTL_COVERAGE_FILES
from suites.frontend.icache.testbenches.shared.coverage.native import NativeCoverageRun
from suites.frontend.icache.testbenches.shared.coverage.native import reset_native_coverage_run
from suites.frontend.icache.testbenches.shared.coverage.native import set_native_coverage_run
from suites.frontend.icache.testbenches.shared.env.pytest_plugins.points import DOMAINS
from suites.frontend.icache.testbenches.shared.env.pytest_plugins.points import domain
from suites.frontend.icache.testbenches.shared.env.pytest_plugins.points import make_report
from suites.frontend.icache.testbenches.shared.env.pytest_plugins.points import feature_catalogue, marker_ids
from suites.frontend.icache.testbenches.shared.env.pytest_plugins.evidence import worst

pytest_plugins = ('toffee._pytest_outcomes',)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption('--bpu-full-suite', action='store_true',
                     help='Require production functional matrices for a successful managed full run')
    parser.addini("toffee_feature_report", "ICache feature evidence JSON", default="")
    parser.addini("toffee_rtl_manifest", "Current-run native coverage manifest",
                  default="results/rtl-coverage-manifest.json")
    parser.addoption("--rtl-retention", choices=("merged", "raw"), default="merged",
                     help="Native coverage retention: bounded merged batches (default), or per-test raw")
    parser.addoption("--rtl-batch-size", type=int, default=16,
                     help="Maximum pending test batch before native merge (default: 16)")
    parser.addoption("--artifact-run", default=None,
                     help="New results/ run directory; enables process-safe testcase outputs and controller evidence")


def pytest_configure(config: pytest.Config) -> None:
    RTL_COVERAGE_FILES.clear()
    root = Path(config.rootpath)
    config.addinivalue_line('markers', 'feature(id): feature label exercised by the test')
    config._bpu_feature_nodes = {}
    config._bpu_feature_phases = {}
    config._bpu_feature_results = defaultdict(dict)
    config._bpu_failed_nodes = set()
    config._bpu_native_run = None
    config._bpu_evidence = None
    managed_output = config.getoption('toffee_output', default=None)
    if managed_output and not config.option.collectonly:
        if config.getoption('artifact_run'):
            raise pytest.UsageError('managed toffee output and legacy --artifact-run cannot be combined')
        from suites.frontend.icache.testbenches.shared.env.pytest_plugins.managed import ManagedFeatures
        config._bpu_evidence = ManagedFeatures(config, managed_output)
        config.pluginmanager.register(config._bpu_evidence, 'bpu-managed-features')
        return
    if config.getoption("rtl_batch_size") < 1:
        raise pytest.UsageError('--rtl-batch-size must be positive')
    if (not config.option.collectonly and not config.getoption('artifact_run')
            and not getattr(config, 'workerinput', None)
            and not getattr(config.option, 'numprocesses', 0)):
        # A plain serial pytest invocation is a selected measurement too.
        # Never let it overwrite the published full-regression reports.
        config.option.artifact_run = str(root / 'results' / f'pytest-{uuid4().hex}')
    if config.getoption("artifact_run"):
        from suites.frontend.icache.testbenches.shared.env.pytest_plugins.evidence import Evidence
        config._bpu_evidence = Evidence(config)
        config.pluginmanager.register(config._bpu_evidence, 'bpu-process-evidence')
        return
    if getattr(config, 'workerinput', None) or getattr(config.option, 'numprocesses', 0):
        raise pytest.UsageError('parallel DUT verification requires --artifact-run to isolate process outputs')
    if not config.option.collectonly and config.getoption("rtl_retention") == "merged":
        if config.getoption("rtl_batch_size") < 1:
            raise pytest.UsageError('--rtl-batch-size must be positive')
        directory = root / 'results' / 'native-runs' / uuid4().hex
        config._bpu_native_run = NativeCoverageRun(directory, batch_size=config.getoption("rtl_batch_size"))
        config._bpu_native_token = set_native_coverage_run(config._bpu_native_run)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item):
    run = item.config._bpu_native_run
    if run is not None:
        run.owner = item.nodeid
    try:
        yield
    finally:
        if run is not None:
            run.end_test(item.nodeid, failed=item.nodeid in item.config._bpu_failed_nodes)


def pytest_unconfigure(config: pytest.Config) -> None:
    token = getattr(config, '_bpu_native_token', None)
    if token is not None:
        reset_native_coverage_run(token)
        del config._bpu_native_token


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    order_tests(items)


def pytest_collection_finish(session: pytest.Session) -> None:
    config = session.config
    if config._bpu_evidence is not None:
        return
    for item in session.items:
        config._bpu_feature_nodes[item.nodeid] = marker_ids(item)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    outcome = yield
    report = outcome.get_result()
    if item.config._bpu_evidence is not None:
        return
    if report.failed:
        item.config._bpu_failed_nodes.add(report.nodeid)
    _record_report(item.config, report)


def _record_report(config: pytest.Config, report: pytest.TestReport) -> None:
    config._bpu_feature_phases.setdefault(report.nodeid, {})[report.when] = phase_record(report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if config.option.collectonly:
        # Discovery is not execution evidence. Preserve the previous formal
        # feature verdicts and raw-file manifest even when collection fails.
        return
    if config._bpu_evidence is not None:
        return
    native = config._bpu_native_run.finish() if config._bpu_native_run is not None else None
    for nodeid, ids in config._bpu_feature_nodes.items():
        phases = config._bpu_feature_phases.get(nodeid, {})
        for identity in ids:
            config._bpu_feature_results[identity][nodeid] = case_status(phases) if phases else 'NOT_RUN'
    features = []
    for feature in feature_catalogue(config._bpu_feature_nodes):
        results = config._bpu_feature_results[feature["id"]]
        status = worst(set(results.values()))
        feature.update(status=status, tests=[{"nodeid": nodeid, "status": result} for nodeid, result in sorted(results.items())], description=feature.get("description", ""))
        features.append(feature)
    report = make_report(features, generated_at=datetime.now(timezone.utc).isoformat())
    path = Path(config.rootpath) / config.getini("toffee_feature_report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = {
        "format": "bpu-rtl-coverage-manifest",
        "version": 1,
        "generated_at": report["generated_at"],
        "pytest_exitstatus": exitstatus,
        "files": [str(item.relative_to(config.rootpath)) for item in sorted(RTL_COVERAGE_FILES)],
        "native_retention": native or {"mode": "raw"},
    }
    manifest_path = Path(config.rootpath) / config.getini("toffee_rtl_manifest")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def pytest_terminal_summary(terminalreporter: Any) -> None:
    config = terminalreporter.config
    if config.option.collectonly:
        terminalreporter.write_line("collection only; existing ICache verification reports preserved")
        return
    if config._bpu_evidence is not None:
        if not config.getoption('toffee_output', default=None):
            terminalreporter.write_line(f"process-isolated ICache evidence: {config.getoption('artifact_run')}")
        return
    results = config._bpu_feature_results
    terminalreporter.write_sep("=", "ICache feature markers (scope=collected-test-markers)")
    for name in DOMAINS:
        collected = [point for point in feature_catalogue(config._bpu_feature_nodes) if domain(point)==name]
        executed = sum(any(state not in ('SKIP', 'NOT_RUN') for state in results[point['id']].values())
                       for point in collected)
        terminalreporter.write_line(f"{name}: executed {executed}/{len(collected)} collected labels; details in {config.getini('toffee_feature_report')}")
