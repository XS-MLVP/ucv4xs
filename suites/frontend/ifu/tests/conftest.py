"""IFU pytest root: expose every DUT harness fixture.

The fixture factories stay in ``suites.frontend.ifu.fixtures``; this file is the
single discovery table so a new DUT adds one import and no nested conftest.
"""

from suites.frontend.ifu.fixtures import frontend_trigger
from suites.frontend.ifu.fixtures import frontend_trigger_factory
from suites.frontend.ifu.fixtures import ifu_agent
from suites.frontend.ifu.fixtures import ifu_agent_factory
from suites.frontend.ifu.fixtures import instr_boundary
from suites.frontend.ifu.fixtures import instr_boundary_factory
from suites.frontend.ifu.fixtures import perf_analysis
from suites.frontend.ifu.fixtures import perf_analysis_factory
from suites.frontend.ifu.fixtures import pred_checker
from suites.frontend.ifu.fixtures import pred_checker_factory
from suites.frontend.ifu.fixtures import rvc_expander
from suites.frontend.ifu.fixtures import rvc_expander_factory
from suites.frontend.ifu.fixtures import uncache_unit
from suites.frontend.ifu.fixtures import uncache_unit_factory


pytest_plugins = ("suites.frontend.ifu.pytest_plugin", "ucv.pytest_selftest")
