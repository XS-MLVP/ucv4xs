"""Function-scoped Picker DUT fixtures with toffee-managed coverage.

The DUT is constructed before the managed runner attaches its coverage file,
so each test starts with an explicit (and therefore covered) reset whose first
active cycle is the one after de-assertion.  Coverage discovery recognises the
``dut`` attribute and calls ``Finish`` before native aggregation, which is why
the fixture never hides the generated object inside a private attribute.
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.harness import DUT_CLASSES, DutHarness


def dut_fixture(name: str):
    @pytest.fixture
    def factory(tmp_path, monkeypatch):
        # Picker may open a default dumpfile even with tracing disabled. Keep
        # that native side effect outside the source tree for the full lifetime.
        monkeypatch.chdir(tmp_path)
        harness = DutHarness(name)
        try:
            yield harness
        finally:
            harness.finish()

    factory.__name__ = f"{name}_harness"
    return factory


rvc_expander = dut_fixture("rvc_expander")
instr_boundary = dut_fixture("instr_boundary")
pred_checker = dut_fixture("pred_checker")
uncache_unit = dut_fixture("uncache_unit")
frontend_trigger = dut_fixture("frontend_trigger")
perf_analysis = dut_fixture("perf_analysis")
ifu = dut_fixture("ifu")
