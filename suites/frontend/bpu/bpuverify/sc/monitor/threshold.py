"""Passive threshold observation; picker/memory-direct details stay outside testcases."""
from bpuverify.common.model.configuration import *
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from operator import index

from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor


class ScThresholdMonitor(CycleMonitor[tuple[int, ...]]):
    def __init__(self, dut, *, ways=SC_WAYS):
        ways = index(ways)
        if ways <= 0:
            raise ValueError('SC threshold monitor needs at least one way')
        names = tuple(memory_signal_names(dut))
        signals = []
        for way in range(ways):
            matches = [name for name in names if name.endswith(f'.Sc.scThreshold_{way}_value')]
            if len(matches) != 1:
                raise RuntimeError(
                    f'SC threshold way {way} needs one memory-direct signal, '
                    f'found {len(matches)}: {matches}'
                )
            # picker lists absolute paths but resolves relative to the top scope.
            signals.append(memory_signal(dut, matches[0].split('.', 1)[1]))
        super().__init__(
            PortBinding(dut.clock, Bundle(thresholds=tuple(signals)), 'sc.thresholds'),
            decoder=lambda sample: tuple(value.as_int() for value in sample.thresholds),
        )

    async def read(self, execution):
        """A bounded @on subscription supplies one immutable clocked snapshot."""
        self.start(execution)
        try:
            return await self.recv()
        finally:
            await self.aclose()
