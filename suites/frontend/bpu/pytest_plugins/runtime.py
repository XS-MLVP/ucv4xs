"""Dependency checks belong to a plugin, not DUT cases or conftest hooks."""
import pytest

from suites.frontend.bpu.runtime.runtime import validate_runtime


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    try:
        validate_runtime()
    except (ImportError, RuntimeError) as error:
        raise pytest.UsageError(str(error)) from error


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield
    report=outcome.get_result()
    reports=getattr(item,'_bpu_body_reports',None)
    if reports is None:
        reports={};item._bpu_body_reports=reports
    reports[report.when]=report.outcome
