"""Replay the entire DCache top-level suite through the DCacheWrapper ports.

This is the strongest practical proof that the wrapper is behaviour-transparent:
the same 20 scenarios, the same reference model and the same assertions, but the
DUT is `DCacheWrapper` and every access goes through its renamed port groups.
Nothing in the scenarios is relaxed for the wrapper.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from dcacheverify.dcache.coverage import DCacheCoverage
from dcacheverify.dcache_wrapper.env import DcacheWrapperEnv

_SCENARIO_FILE = Path(__file__).resolve().parents[1] / "dcache" / "test_dcache.py"
_spec = importlib.util.spec_from_file_location("dcache_scenarios", _SCENARIO_FILE)
_module = importlib.util.module_from_spec(_spec)
sys.modules["dcache_scenarios"] = _module
_spec.loader.exec_module(_module)

for _name in dir(_module):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_module, _name)


@pytest.fixture
def dc(dut_factory):
    """Same scenarios, same DCache coverage groups, DUT = DCacheWrapper."""
    dut = dut_factory("dcache_wrapper")
    env = DcacheWrapperEnv(dut, DCacheCoverage())
    env.reset()
    return env
