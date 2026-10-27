from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.common.env.fixtures import agent_fixture

mbtb_agent = agent_fixture("mbtb", MbtbAgent, max_batch_ticks=128)

from bpuverify.mbtb.agent.cleanup_reset import CleanupResetAgent

mbtb_cleanup_agent = agent_fixture("mbtb", CleanupResetAgent, max_batch_ticks=128)
