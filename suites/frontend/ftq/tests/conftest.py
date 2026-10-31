"""pytest root: one agent fixture per DUT, visible to every test subpackage."""

from __future__ import annotations

from suites.frontend.ftq.commit_queue.agent.main import CommitQueueAgent
from suites.frontend.ftq.fixtures import agent_fixture
from suites.frontend.ftq.ftq.agent.main import FtqAgent
from suites.frontend.ftq.resolve_queue.agent.main import ResolveQueueAgent


pytest_plugins = ("ucv.pytest_selftest",)


resolve_queue_agent = agent_fixture("resolve_queue", ResolveQueueAgent)
commit_queue_agent = agent_fixture("commit_queue", CommitQueueAgent)
ftq_agent = agent_fixture("ftq", FtqAgent)
