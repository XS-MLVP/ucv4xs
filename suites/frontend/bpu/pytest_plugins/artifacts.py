"""Pytest owns the diagnostic switch; scenarios only submit optional traces."""
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.runtime.trace import reset_trace_exports
from suites.frontend.bpu.runtime.trace import set_trace_exports

import pytest


def pytest_addoption(parser):
    parser.getgroup("BPU diagnostics").addoption(
        "--dump-trace", action="store_true", default=False,
        help="Export full cycle diagnostic traces as gzip JSON (default: off).")


def pytest_configure(config):
    config._bpu_trace_export_token = set_trace_exports(config.getoption("dump_trace"))


def pytest_unconfigure(config):
    token = getattr(config, "_bpu_trace_export_token", None)
    if token is not None:
        reset_trace_exports(token)
        del config._bpu_trace_export_token


@pytest.fixture
def abtb_state_output():
    output = output_directory(REPO_ROOT, 'abtb')
    output.mkdir(parents=True, exist_ok=True)
    return output


@pytest.fixture
def bpu_sc_output(request):
    """Keep SC state witnesses beside this run's other BPU artifacts."""
    output = output_directory(request.config.rootpath, 'bpu')
    output.mkdir(parents=True, exist_ok=True)
    return output
