"""Static read-only ABTB write/shadow/SRAM port Bundle; reuse @on mechanics."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal_names
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.abtb.monitor.state.writebuffer import FIELD_NAMES
from bpuverify.bpu.monitor.bypass.monitor import BypassMonitor

ENTRY_NAMES = {name: suffix.removeprefix('entry_')
    for name, suffix in FIELD_NAMES.items() if suffix.startswith('entry_')}


class WriteMonitor(BypassMonitor):
    def __init__(self, agent):
        self.agent, self.subscriptions, self.signal_paths = agent, [], []
        dut = agent.dut
        names = memory_signal_names(dut)
        matches = [name for name in names if name.endswith('.takenCounter_0_0_0_value')]
        if len(matches) != 1:
            raise RuntimeError(f'unique integrated ABTB hierarchy required: {matches!r}')
        prefix = matches[0].split('.', 1)[1].removesuffix('takenCounter_0_0_0_value')

        def signal(name):
            path = prefix + name
            result = memory_signal(dut, path)
            if result is None:
                raise RuntimeError(f'integrated ABTB direct-write native leaf unavailable: {path}')
            self.signal_paths.append(path)
            return result

        def payload(base):
            return Bundle(**{name: signal(base + suffix) for name, suffix in FIELD_NAMES.items()})

        def entry(base):
            return Bundle(**{name: signal(base + suffix) for name, suffix in ENTRY_NAMES.items()})

        def bank(index):
            outer, shadow = f'banks_{index}.', f'banks_{index}.writeBuffer.'
            sram = outer + 'sram.'
            return Bundle(
                slots=tuple(Bundle(shadow_valid=signal(shadow + f'shadowValid_0_{slot}'),
                    dirty=signal(shadow + f'dirty_0_{slot}'),
                    payload=payload(shadow + f'entries_0_{slot}_')) for slot in range(4)),
                plru=signal(shadow + 'state_reg'),
                request=Bundle(valid=signal(outer + 'io_writeReq_valid'),
                    bits=payload(outer + 'io_writeReq_bits_')),
                write=Bundle(valid=signal(shadow + 'io_write_0_valid'),
                    bits=payload(shadow + 'io_write_0_bits_')),
                drain=Bundle(valid=signal(shadow + 'io_read_0_valid'),
                    ready=signal(shadow + 'io_read_0_ready'), bits=payload(shadow + 'io_read_0_bits_')),
                read_input=Bundle(valid=signal(outer + 'io_readReq_valid'),
                    set_index=signal(outer + 'io_readReq_bits_setIdx')),
                reset_done=signal(outer + 'io_sramResetDone'),
                sram=Bundle(ready=signal(sram + 'io_w_req_ready'),
                    write=Bundle(valid=signal(sram + 'io_w_req_valid'),
                        set_index=signal(sram + 'io_w_req_bits_setIdx'),
                        way_mask=signal(sram + 'io_w_req_bits_waymask'),
                        entries=tuple(entry(sram + f'io_w_req_bits_data_{way}_') for way in range(4))),
                    read=tuple(entry(sram + f'io_r_resp_data_{way}_') for way in range(4))))

        self.binding = PortBinding(dut.clock, Bundle(reset=signal('reset'),
            banks=tuple(bank(index) for index in range(4))), 'bpu.integrated_ABTB_direct_write_and_SRAM')

    def start(self, checker):
        if self.subscriptions:
            raise RuntimeError('ABTB write monitor is already started')
        return super().start(checker)
