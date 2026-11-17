"""ResolveQueue fixture ownership."""
from suites.frontend.ftq.testbenches.resolve_queue.env.agent.main import ResolveQueueAgent
from suites.frontend.ftq.testbenches.shared.env.fixtures import agent_fixture, agent_factory

resolve_queue_agent = agent_fixture('resolve_queue', ResolveQueueAgent)
resolve_queue_factory = agent_factory('resolve_queue', ResolveQueueAgent)
