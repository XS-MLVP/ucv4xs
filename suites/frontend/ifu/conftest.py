"""IFU pytest root: register DUT fixture plugins and the shared feature reporter.

Fixture factories live in testbenches/<dut>/tests/fixtures.py; genuinely shared
mechanisms stay under testbenches/shared. This file is the single discovery
table, so a new DUT adds one literal plugin entry and no nested conftest.
"""

pytest_plugins = (
    "suites.frontend.ifu.testbenches.ifu.tests.fixtures",
    "suites.frontend.ifu.testbenches.uncache_unit.tests.fixtures",
    "suites.frontend.ifu.testbenches.frontend_trigger.tests.fixtures",
    "suites.frontend.ifu.testbenches.instr_boundary.tests.fixtures",
    "suites.frontend.ifu.testbenches.rvc_expander.tests.fixtures",
    "suites.frontend.ifu.testbenches.pred_checker.tests.fixtures",
    "suites.frontend.ifu.testbenches.perf_analysis.tests.fixtures",
    "suites.frontend.ifu.testbenches.shared.env.pytest_plugins.features",
    "ucv.pytest_selftest",
)
