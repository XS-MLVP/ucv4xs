"""bpuverify.bpu.monitor.ras.retirement components."""

from toffee import RisingEdge
from toffee import on
from bpuverify.common.monitor.cycle import CycleMonitor


class CommitMonitor(CycleMonitor):
    """Capture before cycle waiters resume, using the existing @on facility."""
    def start(self, execution, *, observer):
        if self._subscription is not None or execution.reactor is None:
            raise RuntimeError('commit monitor requires one active Execution')

        def capture(event):
            observer(self.sample_at(event))

        async def delivered(_):
            pass

        spec = on(RisingEdge(self.binding.clock), delivery='lossless',
                  capacity=self.capacity, capture=capture)(delivered)
        self._execution = execution
        self._subscription = execution.subscribe(spec.bind())
        return self
