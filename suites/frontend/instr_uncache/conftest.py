"""InstrUncache pytest root: register the per-DUT fixture plugins.

The fixture factories live in each testbench's ``tests/fixtures.py``; this file
is the single discovery table so a new DUT adds one literal plugin name and no
nested conftest.
"""

pytest_plugins = (
    "suites.frontend.instr_uncache.testbenches.shared.env.pytest_plugins.feature_report",
    "suites.frontend.instr_uncache.testbenches.instr_uncache_entry.tests.fixtures",
    "suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.tests.fixtures",
    "suites.frontend.instr_uncache.testbenches.instr_uncache.tests.fixtures",
    "ucv.pytest_selftest",
)
