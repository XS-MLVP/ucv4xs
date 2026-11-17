"""Register this verification package's fixtures and reports."""

pytest_plugins = (
    "suites.frontend.ibuffer.testbenches.vtype_gen.tests.fixtures",
    "suites.frontend.ibuffer.testbenches.ibuffer.tests.fixtures",
    "ucv.pytest_features",
    "ucv.pytest_selftest",
)
