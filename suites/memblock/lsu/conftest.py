"""Project-wide pytest root for the LSU UT workspace.

Cross-DUT fixtures are imported from the shared env fixture module; the only
DUT-specific fixture module is registered explicitly below. There is one
pytest root and no per-testbench conftest.py.
"""
from __future__ import annotations

import sys

pytest_plugins = (
    "ucv.pytest_selftest",
    "suites.memblock.lsu.testbenches.store_delay.tests.fixtures",
)

ROOT = __import__('suites.memblock.lsu', fromlist=['ROOT']).ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from suites.memblock.lsu.testbenches.shared.env.fixtures import dut_factory  # noqa: E402,F401
from suites.memblock.lsu.testbenches.shared.env.fixtures import isolated_workdir  # noqa: E402,F401
