"""Register this verification package's fixtures and reports."""

pytest_plugins = (
    "suites.frontend.instr_uncache.testbenches.instr_uncache_entry.tests.fixtures",
    "suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.tests.fixtures",
    "suites.frontend.instr_uncache.testbenches.instr_uncache.tests.fixtures",
    "ucv.pytest_features",
    "ucv.pytest_selftest",
)
