from bpuverify.tage.agent.main import TageAgent
from bpuverify.common.env.fixtures import agent_fixture

tage_agent = agent_fixture("tage", TageAgent, max_batch_ticks=256)
