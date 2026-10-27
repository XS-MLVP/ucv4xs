from bpuverify.ras.agent.main import RasAgent
from bpuverify.common.env.fixtures import agent_fixture

ras_agent = agent_fixture("ras", RasAgent, max_batch_ticks=128)
