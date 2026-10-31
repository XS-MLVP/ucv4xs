"""Reuse exact committed-reset static monitor; no testcase signal access."""
from suites.frontend.bpu.bpu.monitor.bypass import sram_reset as _v6
SramMonitor = _v6.SramMonitor
