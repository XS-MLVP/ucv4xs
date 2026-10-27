"""Passive highest-table write activity; native binding stays inside the agent."""
from bpuverify.common.model.configuration import *
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.monitor.cycle import CycleMonitor


class TageWriteActivityMonitor(CycleMonitor):
    """Capture all banks and ways in one event, including inactive ports."""

    def __init__(self, dut):
        names = tuple(memory_signal_names(dut))

        def signal(bank, field):
            suffix = f'.Tage.tables_{TAGE_TABLES - 1}.tage_entry_write_buffer_bank{bank}.{field}'
            matches = [name for name in names if name.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f'TAGE write signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        banks = tuple(tuple(Bundle(
            valid=signal(bank, f'io_write_{way}_valid'),
            set_idx=signal(bank, f'io_write_{way}_bits_setIdx'),
            tag=signal(bank, f'io_write_{way}_bits_entry_tag'),
            counter=signal(bank, f'io_write_{way}_bits_entry_takenCtr_value'),
            entry_valid=signal(bank, f'io_write_{way}_bits_entry_valid'),
            taken=signal(bank, f'io_takenMask_{way}'),
        ) for way in range(2)) for bank in range(4))
        super().__init__(PortBinding(dut.clock, Bundle(banks=banks), 'tage.highest_table_writes'),
                         decoder=self.decode)

    @staticmethod
    def decode(sample):
        banks = tuple(tuple({field: getattr(port, field).as_int()
                             for field in ('set_idx', 'tag', 'counter', 'entry_valid', 'taken')}
                            if port.valid.as_int() else None for port in bank)
                      for bank in sample.banks)
        return {'banks': banks}
