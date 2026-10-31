"""Dependency checks belong to a plugin, not DUT cases or conftest hooks."""
import pytest

from suites.frontend.icache.runtime.runtime import validate_runtime


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    try:
        validate_runtime()
    except (ImportError, RuntimeError) as error:
        raise pytest.UsageError(str(error)) from error
