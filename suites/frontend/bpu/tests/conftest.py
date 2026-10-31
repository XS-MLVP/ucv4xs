"""BPU pytest root: one agent fixture per real DUT.

Agent fixtures live here, not in per-DUT ``<dut>/env/pytest.py``
modules or per-directory ``conftest.py`` files.  A DUT fixture owns the native
DUT, the Execution context, and the agent; tests only call the agent
transaction API.  Non-agent pytest fixtures belong to the plugin modules
registered below, so this file stays a registration table.
"""

from __future__ import annotations

from suites.frontend.bpu.abtb.agent.main import AbtbAgent
from suites.frontend.bpu.bpu.agent.main import BpuAgent
from suites.frontend.bpu.runtime.fixtures import agent_fixture
from suites.frontend.bpu.runtime.fixtures import dut_factory
from suites.frontend.bpu.ittage.agent.main import IttageAgent
from suites.frontend.bpu.mbtb.agent.cleanup_reset import CleanupResetAgent
from suites.frontend.bpu.mbtb.agent.main import MbtbAgent
from suites.frontend.bpu.ras.agent.main import RasAgent
from suites.frontend.bpu.sc.agent.main import ScAgent
from suites.frontend.bpu.tage.agent.main import TageAgent
from suites.frontend.bpu.ubtb.agent.main import UbtbAgent
from suites.frontend.bpu.uras.agent.main import UrasAgent
from suites.frontend.bpu.utage.agent.main import UtageAgent


pytest_plugins = ('suites.frontend.bpu.pytest_plugins.runtime', 'suites.frontend.bpu.pytest_plugins.features',
                  'suites.frontend.bpu.pytest_plugins.artifacts', 'suites.frontend.bpu.pytest_plugins.regression',
                  'suites.frontend.bpu.pytest_plugins.isolation', 'ucv.pytest_selftest')

abtb_agent = agent_fixture("abtb", AbtbAgent, max_batch_ticks=128)
bpu_agent = agent_fixture("bpu", BpuAgent, max_batch_ticks=256)
ittage_agent = agent_fixture("ittage", IttageAgent, max_batch_ticks=256)
mbtb_agent = agent_fixture("mbtb", MbtbAgent, max_batch_ticks=128)
mbtb_cleanup_agent = agent_fixture("mbtb", CleanupResetAgent, max_batch_ticks=128)
ras_agent = agent_fixture("ras", RasAgent, max_batch_ticks=128)
sc_agent = agent_fixture("sc", ScAgent, max_batch_ticks=256)
tage_agent = agent_fixture("tage", TageAgent, max_batch_ticks=256)
ubtb_agent = agent_fixture("ubtb", UbtbAgent, max_batch_ticks=128)
uras_agent = agent_fixture("uras", UrasAgent, max_batch_ticks=128)
utage_agent = agent_fixture("utage", UtageAgent, max_batch_ticks=256)
