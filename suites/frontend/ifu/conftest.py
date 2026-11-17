"""Register this verification package's fixtures and reports."""

pytest_plugins = (
    "suites.frontend.ifu.testbenches.rvc_expander.tests.fixtures",
    "suites.frontend.ifu.testbenches.instr_boundary.tests.fixtures",
    "suites.frontend.ifu.testbenches.pred_checker.tests.fixtures",
    "suites.frontend.ifu.testbenches.uncache_unit.tests.fixtures",
    "suites.frontend.ifu.testbenches.frontend_trigger.tests.fixtures",
    "suites.frontend.ifu.testbenches.perf_analysis.tests.fixtures",
    "suites.frontend.ifu.testbenches.ifu.tests.fixtures",
    "ucv.pytest_features",
    "ucv.pytest_selftest",
)
