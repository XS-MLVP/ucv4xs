from bpuverify.ittage.agent.main import IttageAgent
from bpuverify.common.env.fixtures import agent_fixture

ittage_agent = agent_fixture("ittage", IttageAgent, max_batch_ticks=256)
