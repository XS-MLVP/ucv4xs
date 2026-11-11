"""BPU pytest root: one agent fixture per real DUT.

Agent fixtures live here, not in per-DUT ``<dut>/env/pytest.py``
modules or per-directory ``conftest.py`` files.  A DUT fixture owns the native
DUT, the Execution context, and the agent; tests only call the agent
transaction API.  Non-agent pytest fixtures belong to the plugin modules
registered below, so this file stays a registration table.
"""

from __future__ import annotations

from suites.frontend.bpu.testbenches.abtb.env.agent.main import AbtbAgent
from suites.frontend.bpu.testbenches.abtb.tests.fixtures import abtb_state_output
from suites.frontend.bpu.testbenches.bpu.tests.fixtures import bpu_sc_output
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.agent import BpuScenarioAgent as BpuAgent
from suites.frontend.bpu.testbenches.shared.env.fixtures import agent_fixture
from suites.frontend.bpu.testbenches.shared.env.fixtures import dut_factory
from suites.frontend.bpu.testbenches.ittage.env.agent.main import IttageAgent
from suites.frontend.bpu.testbenches.mbtb.env.agent.cleanup_reset import CleanupResetAgent
from suites.frontend.bpu.testbenches.mbtb.env.agent.main import MbtbAgent
from suites.frontend.bpu.testbenches.ras.env.agent.main import RasAgent
from suites.frontend.bpu.testbenches.sc.env.agent.main import ScAgent
from suites.frontend.bpu.testbenches.tage.env.agent.main import TageAgent
from suites.frontend.bpu.testbenches.ubtb.env.agent.main import UbtbAgent
from suites.frontend.bpu.testbenches.uras.env.agent.main import UrasAgent
from suites.frontend.bpu.testbenches.utage.env.agent.main import UtageAgent


pytest_plugins = ('suites.frontend.bpu.testbenches.shared.env.pytest_plugins.runtime', 'suites.frontend.bpu.testbenches.shared.env.pytest_plugins.features',
                  'suites.frontend.bpu.testbenches.shared.env.pytest_plugins.artifacts', 'suites.frontend.bpu.testbenches.shared.env.pytest_plugins.regression',
                  'suites.frontend.bpu.testbenches.shared.env.pytest_plugins.isolation',
                  'suites.frontend.bpu.testbenches.bpu.tests.regression',
                  'suites.frontend.bpu.testbenches.mbtb.tests.regression',
                  'suites.frontend.bpu.tools.parallel_coverage', 'ucv.pytest_selftest')

abtb_agent = agent_fixture("abtb", AbtbAgent, max_batch_ticks=128)
bpu_agent = agent_fixture("bpu", BpuAgent, max_batch_ticks=256)
ittage_agent = agent_fixture("ittage", IttageAgent, max_batch_ticks=256)
mbtb_agent = agent_fixture("mbtb", MbtbAgent, max_batch_ticks=128, checked_close=True)
mbtb_cleanup_agent = agent_fixture("mbtb", CleanupResetAgent, max_batch_ticks=128, checked_close=True)
ras_agent = agent_fixture("ras", RasAgent, max_batch_ticks=128)
sc_agent = agent_fixture("sc", ScAgent, max_batch_ticks=256)
tage_agent = agent_fixture("tage", TageAgent, max_batch_ticks=256)
ubtb_agent = agent_fixture("ubtb", UbtbAgent, max_batch_ticks=128)
uras_agent = agent_fixture("uras", UrasAgent, max_batch_ticks=128)
utage_agent = agent_fixture("utage", UtageAgent, max_batch_ticks=256)
