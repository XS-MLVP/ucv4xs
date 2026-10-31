"""Lossless @on observation, sampled before cycle waiters resume."""
from toffee import RisingEdge, on
from suites.frontend.bpu.monitors.cycle import CycleMonitor


class MicroRasMonitor(CycleMonitor):
    def start(self, execution, *, observer):
        if self._subscription is not None or execution.reactor is None:
            raise RuntimeError('MicroRAS monitor requires one active Execution')
        def capture(event):
            observer(self.sample_at(event))
        async def delivered(_):
            pass
        spec = on(RisingEdge(self.binding.clock), delivery='lossless',
            capacity=self.capacity, capture=capture)(delivered)
        self._execution = execution
        self._subscription = execution.subscribe(spec.bind())
        return self
