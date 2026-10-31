"""Existing static memory-direct binding, with only one immutable snapshot."""
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.utage.bundle.values import _plain
from suites.frontend.bpu.utage.monitor.shadow import UtageShadowMonitor


class LearningRetentionMonitor(CycleMonitor):
    def __init__(self, agent):
        _, _, binding = UtageShadowMonitor._bind(agent, 1)
        super().__init__(binding, decoder=_plain)
        self.latest = None

    def observe(self, observation):
        self.latest = observation
