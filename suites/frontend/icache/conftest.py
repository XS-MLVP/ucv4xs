"""ICache pytest root: one agent fixture per real DUT.

Fixture wiring lives here.  Per-DUT verification packages keep agents,
drivers, monitors, checkers and transactions, but do not export pytest setup
from an ``env/pytest.py`` module or a per-directory conftest.
"""

from __future__ import annotations

from suites.frontend.icache.testbenches.shared.env.fixtures import agent_fixture
from suites.frontend.icache.testbenches.shared.env.fixtures import dut_factory
from suites.frontend.icache.testbenches.dataarray.env.agent.main import DataArrayAgent
from suites.frontend.icache.testbenches.databank.env.agent.main import DataBankAgent
from suites.frontend.icache.testbenches.icache.env.agent.main import ICacheAgent
from suites.frontend.icache.testbenches.mainpipe.env.agent.main import MainPipeAgent
from suites.frontend.icache.testbenches.metaarray.env.agent.main import MetaArrayAgent
from suites.frontend.icache.testbenches.metabank.env.agent.main import MetaBankAgent
from suites.frontend.icache.testbenches.missunit.env.agent.main import MissUnitAgent
from suites.frontend.icache.testbenches.mshr.env.agent.main import MshrAgent
from suites.frontend.icache.testbenches.prefetchpipe.env.agent.main import PrefetchPipeAgent
from suites.frontend.icache.testbenches.replacer.env.agent.main import ReplacerAgent
from suites.frontend.icache.testbenches.waylookup.env.agent.main import WayLookupAgent


pytest_plugins = ('suites.frontend.icache.testbenches.shared.env.pytest_plugins.runtime', 'suites.frontend.icache.testbenches.shared.env.pytest_plugins.features',
                  'suites.frontend.icache.testbenches.shared.env.pytest_plugins.artifacts', 'suites.frontend.icache.testbenches.shared.env.pytest_plugins.regression',
                  'suites.frontend.icache.tools.parallel_coverage_plugin', 'ucv.pytest_selftest')

dataarray_agent = agent_fixture("dataarray", DataArrayAgent, max_batch_ticks=64)
databank_agent = agent_fixture("databank", DataBankAgent, max_batch_ticks=64, checked=True)
icache_agent = agent_fixture("icache", ICacheAgent, max_batch_ticks=64)
mainpipe_agent = agent_fixture("mainpipe", MainPipeAgent, max_batch_ticks=64)
metaarray_agent = agent_fixture("metaarray", MetaArrayAgent, max_batch_ticks=64)
metabank_agent = agent_fixture("metabank", MetaBankAgent, max_batch_ticks=64, checked=True)
missunit_agent = agent_fixture("missunit", MissUnitAgent, max_batch_ticks=64)
mshr_agent = agent_fixture("mshr", MshrAgent, max_batch_ticks=64)
prefetchpipe_agent = agent_fixture("prefetchpipe", PrefetchPipeAgent, max_batch_ticks=64)
replacer_agent = agent_fixture("replacer", ReplacerAgent, max_batch_ticks=64)
waylookup_agent = agent_fixture("waylookup", WayLookupAgent, max_batch_ticks=64)
