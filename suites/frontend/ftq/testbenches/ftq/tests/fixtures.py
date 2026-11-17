"""FTQ fixture ownership."""
from suites.frontend.ftq.testbenches.ftq.env.agent.main import FtqAgent
from suites.frontend.ftq.testbenches.ftq.env.harness import FtqDutHarness
from suites.frontend.ftq.testbenches.shared.env.fixtures import agent_fixture, agent_factory

ftq_agent = agent_fixture('ftq', FtqAgent, dut_type=FtqDutHarness)
ftq_factory = agent_factory('ftq', FtqAgent, dut_type=FtqDutHarness)
