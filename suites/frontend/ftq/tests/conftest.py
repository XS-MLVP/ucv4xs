"""pytest root: one agent fixture per DUT, visible to every test subpackage."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.commit_queue.agent.main import CommitQueueAgent
from suites.frontend.ftq.fixtures import agent_fixture, agent_factory
from suites.frontend.ftq.ftq.agent.main import FtqAgent
from suites.frontend.ftq.resolve_queue.agent.main import ResolveQueueAgent


pytest_plugins = ("ucv.pytest_selftest",)


resolve_queue_agent = agent_fixture("resolve_queue", ResolveQueueAgent)
resolve_queue_factory = agent_factory('resolve_queue', ResolveQueueAgent)
commit_queue_agent = agent_fixture("commit_queue", CommitQueueAgent)
commit_queue_factory = agent_factory('commit_queue', CommitQueueAgent)
ftq_agent = agent_fixture("ftq", FtqAgent)
ftq_factory = agent_factory('ftq', FtqAgent)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    reports = getattr(item, '_ftq_reports', {})
    reports[report.when] = report.outcome
    item._ftq_reports = reports
