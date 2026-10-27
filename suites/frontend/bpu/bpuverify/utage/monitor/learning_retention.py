"""Existing static memory-direct binding, with only one immutable snapshot."""
from bpuverify.common.monitor.cycle import CycleMonitor
from bpuverify.utage.bundle.values import _plain
from bpuverify.utage.monitor.shadow import UtageShadowMonitor


class LearningRetentionMonitor(CycleMonitor):
    def __init__(self, agent):
        _, _, binding = UtageShadowMonitor._bind(agent, 1)
        super().__init__(binding, decoder=_plain)
        self.latest = None

    def observe(self, observation):
        self.latest = observation
