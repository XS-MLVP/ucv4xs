"""One suite pytest root: explicit plugin registration only."""
pytest_plugins = (
    'ucv.pytest_selftest',
    'suites.vector.vagq.testbenches.shared.env.pytest_plugins.runtime',
    'suites.vector.vagq.testbenches.addrgen.tests.fixtures',
    'suites.vector.vagq.testbenches.arbiter.tests.fixtures',
    'suites.vector.vagq.testbenches.entrytable.tests.fixtures',
    'suites.vector.vagq.testbenches.manager.tests.fixtures',
    'suites.vector.vagq.testbenches.maskgen.tests.fixtures',
    'suites.vector.vagq.testbenches.merge.tests.fixtures',
    'suites.vector.vagq.testbenches.ordered.tests.fixtures',
    'suites.vector.vagq.testbenches.pipeline.tests.fixtures',
    'suites.vector.vagq.testbenches.split.tests.fixtures',
    'suites.vector.vagq.testbenches.storedata.tests.fixtures',
    'suites.vector.vagq.testbenches.vagq.tests.fixtures',
)
