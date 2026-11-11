"""IBuffer pytest root: register the only suite-level pytest plugins.

Each DUT owns its agent fixture in ``tests/fixtures.py``; the shared feature
plugin aggregates collected feature labels.  This file is the single literal
registration table and contains no second discovery tree.
"""

pytest_plugins = (
    "suites.frontend.ibuffer.testbenches.ibuffer.tests.fixtures",
    "suites.frontend.ibuffer.testbenches.vtype_gen.tests.fixtures",
    "suites.frontend.ibuffer.testbenches.shared.env.pytest_plugins.features",
    "ucv.pytest_selftest",
)
