from bpuverify.utage.agent.main import UtageAgent
from bpuverify.common.env.fixtures import agent_fixture

utage_agent = agent_fixture("utage", UtageAgent, max_batch_ticks=256)
