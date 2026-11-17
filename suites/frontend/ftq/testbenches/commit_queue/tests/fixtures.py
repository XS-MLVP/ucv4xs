"""Historical CommitQueue fixture ownership; current binding availability is in the spec."""
from suites.frontend.ftq.testbenches.commit_queue.env.agent.main import CommitQueueAgent
from suites.frontend.ftq.testbenches.commit_queue.env.harness import CommitQueueDutHarness
from suites.frontend.ftq.testbenches.shared.env.fixtures import agent_fixture, agent_factory

commit_queue_agent = agent_fixture('commit_queue', CommitQueueAgent, dut_type=CommitQueueDutHarness)
commit_queue_factory = agent_factory('commit_queue', CommitQueueAgent, dut_type=CommitQueueDutHarness)
