"""Pytest owns the diagnostic switch; scenarios only submit optional traces."""
from suites.frontend.icache.runtime.trace import reset_trace_exports
from suites.frontend.icache.runtime.trace import set_trace_exports


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
