"""Classify project self-checks without changing hardware feature verdicts.

A suite opts in with ``pytest_plugins = ("ucv.pytest_selftest",)``.  The
marker is registered in the suite's ``pytest.ini``; it only supports selection
and reporting.  It does not rewrite any case verdict or feature-point credit.
"""
from __future__ import annotations

from pathlib import Path

import pytest


SELFTEST_DIRS = frozenset({'framework', 'checkers', 'selftest', 'diagnostics'})


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'selftest: environment, checker or diagnostic self-check; never hardware functional credit',
    )


def pytest_collection_modifyitems(items):
    for item in items:
        parts = Path(item.nodeid.split('::', 1)[0]).parts
        if any(part in SELFTEST_DIRS for part in parts[:-1]):
            item.add_marker(pytest.mark.selftest)
