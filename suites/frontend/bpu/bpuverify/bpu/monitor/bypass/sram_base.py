"""Extend the static shadow Bundle with table and SRAM bank boundaries."""
from bpuverify.common.env.memory_direct import memory_signal
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.monitor.bypass.monitor import BypassMonitor


class SramMonitor(BypassMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        tables = []
        for shadow_prefix in self.prefixes:
            prefix = shadow_prefix.removesuffix('wbuffer.')
            def signal(field, prefix=prefix):
                value = memory_signal(agent.dut, prefix + field)
                if value is None:
                    raise RuntimeError(f'integrated SRAM memory-direct leaf unavailable: {prefix + field}')
                return value
            def data(base):
                return Bundle(data_valid=signal(base + '_valid'), tag=signal(base + '_tag'),
                    position=signal(base + '_cfiPosition'), counter=signal(base + '_takenCtr_value'))
            banks = []
            for bank in range(4):
                base = f'utage_entry_sram_bank{bank}.'
                banks.append(Bundle(read_valid=signal(base + 'io_r_req_valid'),
                    read_set=signal(base + 'io_r_req_bits_setIdx'),
                    write_valid=signal(base + 'io_w_req_valid'), write_set=signal(base + 'io_w_req_bits_setIdx'),
                    write_data=data(base + 'io_w_req_bits_data_0'),
                    reset_active=signal(base + '_resetState'), reset_set=signal(base + '_resetSet'),
                    reset_done=signal(base + 'io_resetDone'), ren=signal(base + 'ren'), wen=signal(base + 'wen'),
                    array=Bundle(address=signal(base + 'array.RW0_addr'), enable=signal(base + 'array.RW0_en'),
                        write=signal(base + 'array.RW0_wmode'), data=signal(base + 'array.RW0_wdata')),
                    response=data(base + 'io_r_resp_data_0')))
            tables.append(Bundle(read_index=signal('io_req_bits_readIndex'), reset_done=signal('io_sramResetDone'),
                bank_mask=signal('a1_bankOH'), conflict=signal('needCheckConflict'), write_mask=signal('writeOHNext'),
                response=data('io_resps_readEntry'), banks=tuple(banks)))
        bits = self.binding.bits
        self.binding = PortBinding(agent.dut.clock,
            Bundle(reset=bits.reset, tables=bits.tables, sram=tuple(tables)), 'bpu.integrated_microtage_sram')
