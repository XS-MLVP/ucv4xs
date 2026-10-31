"""Read-only static memory-direct Bundle with coherent @on capture and direct Scoreboard."""
from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from copy import deepcopy

from toffee import Bundle
from toffee import CheckContext
from toffee import RisingEdge
from toffee import Scoreboard
from toffee import ScoreboardMode
from toffee import on
from suites.frontend.bpu.abtb.bundle.values import _plain
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor


class ReplacerMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        candidates = [name for name in names if name.endswith('.replacers_0.io_readValid')]
        if len(candidates) != 1:
            raise RuntimeError(f'unique replacer hierarchy required: {candidates!r}')
        prefix = candidates[0].split('.', 1)[1].removesuffix('replacers_0.io_readValid')

        def signal(name):
            result = memory_signal(dut, prefix + name)
            if result is None:
                raise RuntimeError(f'ABTB memory-direct leaf unavailable: {prefix + name}')
            return result

        def bank(index):
            base = f'replacers_{index}.'
            return Bundle(read_valid=signal(base + 'io_readValid'),
                read_set=signal(base + 'io_readSetIdx'),
                read_mask=tuple(signal(base + f'io_readWayMask_{way}') for way in range(4)),
                write_valid=signal(base + 'io_writeValid'),
                write_set=signal(base + 'io_writeSetIdx'),
                write_way=signal(base + 'io_writeWayIdx'),
                replace_set=signal(base + 'io_replaceSetIdx'),
                victim=signal(base + 'io_victimWayIdx'),
                states=tuple(signal(base + f'states.states_{s}') for s in range(64)),
                shadow=tuple(signal(base + f'state_vec_{s}') for s in range(64)))

        self.prefix = prefix
        super().__init__(PortBinding(dut.clock,
            Bundle(reset=dut.reset, banks=tuple(bank(b) for b in range(4))),
            'abtb.replacer_observation'), decoder=_plain)

    def start(self, execution, *, observer):
        if self._subscription is not None or execution.reactor is None:
            raise RuntimeError('replacer monitor requires a new active subscription')

        def capture(event):
            observer(self.sample_at(event))

        async def delivered(_):
            pass

        spec = on(RisingEdge(self.binding.clock), delivery='lossless',
                  capacity=self.capacity, capture=capture)(delivered)
        self._subscription = execution.subscribe(spec.bind())
        self._execution = execution
        return self
