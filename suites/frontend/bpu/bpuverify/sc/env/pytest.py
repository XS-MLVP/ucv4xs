from bpuverify.sc.agent.main import ScAgent
from bpuverify.common.env.fixtures import agent_fixture

sc_agent = agent_fixture("sc", ScAgent, max_batch_ticks=256)
