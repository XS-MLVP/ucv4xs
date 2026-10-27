from bpuverify.ubtb.agent.main import UbtbAgent
from bpuverify.common.env.fixtures import agent_fixture

ubtb_agent = agent_fixture("ubtb", UbtbAgent, max_batch_ticks=128)
