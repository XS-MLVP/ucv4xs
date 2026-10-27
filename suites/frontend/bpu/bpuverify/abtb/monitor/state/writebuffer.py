"""Static full-payload memory-direct Bundle plus coherent synchronous @on capture."""
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle
from bpuverify.abtb.bundle.values import _plain
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.abtb.monitor.state.counter import CounterMonitor

FIELD_NAMES = dict(need_reset='needResetCtr', set_index='setIdx', way='wayIdx', valid='entry_valid',
    tag='entry_tag', position='entry_position', branch_type='entry_attribute_branchType',
    ras_action='entry_attribute_rasAction', target_low='entry_targetLowerBits')


class CapacityMonitor(CounterMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        counter_bits = self.binding.bits
        dut = agent.dut
        names = tuple(memory_signal_names(dut))
        match, = [name for name in names if name.endswith('.takenCounter_0_0_0_value')]
        prefix = match.split('.', 1)[1].removesuffix('takenCounter_0_0_0_value')

        def signal(name):
            value = memory_signal(dut, prefix + name)
            if value is None:
                raise RuntimeError(f'ABTB capacity memory-direct signal unavailable: {prefix + name}')
            return value

        def payload(base):
            return Bundle(**{name: signal(base + suffix) for name, suffix in FIELD_NAMES.items()})

        def bank(index):
            outer = f'banks_{index}.'
            base = outer + 'writeBuffer.'
            slots = tuple(Bundle(shadow_valid=signal(base + f'shadowValid_0_{slot}'),
                dirty=signal(base + f'dirty_0_{slot}'), payload=payload(base + f'entries_0_{slot}_')) for slot in range(4))
            return Bundle(slots=slots, plru=signal(base + 'state_reg'),
                write=Bundle(valid=signal(base + 'io_write_0_valid'), bits=payload(base + 'io_write_0_bits_')),
                drain=Bundle(valid=signal(base + 'io_read_0_valid'), ready=signal(base + 'io_read_0_ready'),
                             bits=payload(base + 'io_read_0_bits_')),
                read_pressure=signal(outer + 'io_readReq_valid'), reset_done=signal(outer + 'io_sramResetDone'))

        self.binding = PortBinding(dut.clock, Bundle(counter=counter_bits, banks=tuple(bank(i) for i in range(4))),
                                   'abtb.write_buffer_capacity')
        self.decoder = self.decode

    @staticmethod
    def decode(snapshot):
        row = _plain(snapshot)
        if not row['counter']['training']['valid']:
            row['counter']['training']['bits'] = None
        for bank in row['banks']:
            if not bank['write']['valid']:
                bank['write']['bits'] = None
            if not (bank['drain']['valid'] and bank['drain']['ready']):
                bank['drain']['bits'] = None
        return row
