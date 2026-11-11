"""Pytest hook for the BPU-derived parallel coverage acceptance.

The acceptance implementation stays in parallel_coverage.py.  Import it only
when a managed full-suite run requests it, so ordinary collection and DUT runs
do not import another suite's testbenches.
"""
import pytest


@pytest.hookimpl(optionalhook=True, tryfirst=True)
def pytest_toffee_coverage(config, functional, native, pytest_exitstatus):
    if config.getoption('bpu_full_suite') and pytest_exitstatus == 0:
        from suites.frontend.icache.tools.parallel_coverage import validate_parallel_case_coverage
        validate_parallel_case_coverage(functional, profile=config.getoption('regression_profile'))
