"""suites.frontend.bpu.utage.monitor.shadow components."""

from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from toffee import Bundle
from toffee.signals import signal_width
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.utage.bundle.values import _plain


class UtageShadowMonitor(CycleMonitor):
    def __init__(self, agent, *, table):
        self.prefix, self.tag_width, binding = self._bind(agent, table)
        self.trace = []
        self.latest = None
        super().__init__(binding, decoder=_plain)

    @staticmethod
    def _bind(agent, table):
        if type(table) is not int or table not in (0, 1):
            raise ValueError('shadow table must be0or1')
        cache = getattr(agent, '_utage_shadow_bindings_v1', None)
        if cache is None:
            cache = {}
            agent._utage_shadow_bindings_v1 = cache
        if table in cache:
            return cache[table]
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        suffix = '' if table == 0 else '_1'
        ending = f'MicroTageTable{suffix}.wbuffer.enqPtr_value'
        matches = [name for name in names if name.endswith(ending)]
        if len(matches) != 1:
            raise RuntimeError(f'unique shadow table{table} memory-direct binding required; got{matches!r}')
        prefix = matches[0].split('.', 1)[1].removesuffix('enqPtr_value')

        def signal(field):
            return memory_signal(dut, prefix + field)

        cells = tuple(Bundle(valid=signal(f'entries_{slot}_valid'), index=signal(f'entries_{slot}_index'),
            data_valid=signal(f'entries_{slot}_entryData_bits_valid'), tag=signal(f'entries_{slot}_entryData_bits_tag'),
            position=signal(f'entries_{slot}_entryData_bits_cfiPosition'),
            counter=signal(f'entries_{slot}_entryData_bits_takenCtr_value')) for slot in range(8))
        binding = PortBinding(dut.clock, Bundle(public=Bundle(
            valid=agent.ports.training_observation.valid,
            bits=agent.ports.training_observation.bits), cells=cells, mask=signal('priorityMask'), enq=signal('enqPtr_value'),
            chosen_first=signal('a1_chosenFirstMask'), hits=tuple(signal(f'a1_entryHit_{slot}') for slot in range(8)),
            response=Bundle(hit=signal('io_resp_hit'), valid=signal('io_resp_readEntry_valid'),
                tag=signal('io_resp_readEntry_tag'), position=signal('io_resp_readEntry_cfiPosition'),
                counter=signal('io_resp_readEntry_takenCtr_value'))), 'utage.shadow_observation')
        cache[table] = (prefix, signal_width(cells[0].tag), binding)
        return cache[table]

    def observe(self, observation):
        self.latest = observation.value
        self.trace.append(dict(tick=observation.event.tick, **observation.value))
