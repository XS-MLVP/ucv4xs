"""Read-only actual gate witnesses share the established phase adapter."""
from collections import OrderedDict

from suites.frontend.bpu.sc.monitor.eligibility import EligibilityInputMonitor


class EnableInputMonitor(EligibilityInputMonitor):
    def __init__(self,agent):
        super().__init__(agent)
        self.enabled=OrderedDict()

    def capture_input(self,event,events):
        if events.reset:self.enabled.clear()
        self.enabled[event.tick+1]=events.enabled
        while len(self.enabled)>64:self.enabled.popitem(last=False)
        super().capture_input(event,events)

    def enabled_at(self,tick):
        if self.failure is not None:raise self.failure
        if tick not in self.enabled:raise AssertionError(f'no actual SC enable witness at tick {tick}')
        return self.enabled[tick]
