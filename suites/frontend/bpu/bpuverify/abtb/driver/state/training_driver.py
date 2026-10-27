"""Input-only asynchronous pulse; return the monitor's actual acceptance event."""
from toffee import AsyncDriver
from toffee import ClockCycles
from toffee.data import drive_data
from toffee.data import iter_data_leaves


class AcceptedPulseDriver(AsyncDriver):
    def __init__(self, binding, *, checker):
        self.binding, self.checker = binding, checker
        signals = (binding.valid, *(leaf for _, leaf in iter_data_leaves(binding.bits, binding.name)))
        super().__init__(signals, name=binding.name + '.accepted-pulse')

    async def _drive_one(self, transaction):
        begin = len(self.checker.accepted_events)
        try:
            drive_data(self.binding.bits, transaction, self.binding.name)
            self.binding.valid.Set(1)
            await ClockCycles(self.binding.clock, 1)
        finally:
            self.binding.valid.Set(0)
        await ClockCycles(self.binding.clock, 1)
        self.checker.raise_failure()
        self.checker.check(begin + 1, len(self.checker.accepted_events), phase='one-actual-pulse-acceptance')
        return self.checker.accepted_events[-1]
