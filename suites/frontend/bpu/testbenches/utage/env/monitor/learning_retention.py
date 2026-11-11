"""Existing static memory-direct binding, with only one immutable snapshot."""
from suites.frontend.bpu.testbenches.shared.env.monitor.cycle import CycleMonitor
from suites.frontend.bpu.testbenches.utage.env.bundle.values import _plain
from suites.frontend.bpu.testbenches.utage.env.monitor.shadow import UtageShadowMonitor


class LearningRetentionMonitor(CycleMonitor):
    def __init__(self, agent):
        _, _, binding = UtageShadowMonitor._bind(agent, 1)
        super().__init__(binding, decoder=_plain)
        self.latest = None

    def observe(self, observation):
        self.latest = observation
