from bpuverify.uras.agent.main import UrasAgent
from bpuverify.common.env.fixtures import agent_fixture

uras_agent = agent_fixture("uras", UrasAgent, max_batch_ticks=128)
