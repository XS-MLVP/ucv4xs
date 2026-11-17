"""Register this verification package's fixtures and reports."""
import pytest

pytest_plugins = (
    "suites.frontend.ftq.testbenches.resolve_queue.tests.fixtures",
    "suites.frontend.ftq.testbenches.commit_queue.tests.fixtures",
    "suites.frontend.ftq.testbenches.ftq.tests.fixtures",
    "ucv.pytest_features",
    "ucv.pytest_selftest",
)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Preserve strict finish without duplicating a reported body failure."""
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, '_ftq_reports', {})
    reports[report.when] = report.outcome
    item._ftq_reports = reports
