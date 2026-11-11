"""pytest root: one agent fixture per DUT, visible to every test subpackage."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.testbenches.commit_queue.env.agent.main import CommitQueueAgent
from suites.frontend.ftq.testbenches.commit_queue.env.harness import CommitQueueDutHarness
from suites.frontend.ftq.testbenches.shared.env.fixtures import agent_fixture
from suites.frontend.ftq.testbenches.shared.env.fixtures import agent_factory
from suites.frontend.ftq.testbenches.ftq.env.agent.main import FtqAgent
from suites.frontend.ftq.testbenches.ftq.env.harness import FtqDutHarness
from suites.frontend.ftq.testbenches.resolve_queue.env.agent.main import ResolveQueueAgent


pytest_plugins = ("ucv.pytest_selftest",)


resolve_queue_agent = agent_fixture("resolve_queue", ResolveQueueAgent)
resolve_queue_factory = agent_factory('resolve_queue', ResolveQueueAgent)
commit_queue_agent = agent_fixture(
    "commit_queue", CommitQueueAgent, dut_type=CommitQueueDutHarness)
commit_queue_factory = agent_factory(
    'commit_queue', CommitQueueAgent, dut_type=CommitQueueDutHarness)
ftq_agent = agent_fixture("ftq", FtqAgent, dut_type=FtqDutHarness)
ftq_factory = agent_factory('ftq', FtqAgent, dut_type=FtqDutHarness)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, '_ftq_reports', {})
    reports[report.when] = report.outcome
    item._ftq_reports = reports
