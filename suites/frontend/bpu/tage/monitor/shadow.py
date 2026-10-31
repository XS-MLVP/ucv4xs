"""Read-only, same-event TAGE shadow ownership and drain arbitration."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from toffee import Bundle

from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.tage.model.shadow import SLOT_FIELDS


class TageShadowMonitor(CycleMonitor):
    """Snapshot every bank/owner/depth; never derive expected state here."""

    def __init__(self, dut, *, table=TAGE_TABLES - 1):
        if not isinstance(table, int) or not 0 <= table < TAGE_TABLES:
            raise ValueError('TAGE shadow table must be a configured table')
        names = tuple(memory_signal_names(dut))

        def signal(bank, field):
            suffix = f'.Tage.tables_{table}.tage_entry_write_buffer_bank{bank}.{field}'
            matches = [name for name in names if name.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f'TAGE shadow signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        def slot(bank, owner, depth):
            prefix = f'entries_{owner}_{depth}_'
            return Bundle(valid=signal(bank, f'shadowValid_{owner}_{depth}'),
                dirty=signal(bank, f'dirty_{owner}_{depth}'),
                set_idx=signal(bank, prefix+'setIdx'),
                tag=signal(bank, prefix+'entry_tag'),
                entry_valid=signal(bank, prefix+'entry_valid'),
                counter=signal(bank, prefix+'entry_takenCtr_value'))

        banks = tuple(Bundle(shadow=tuple(tuple(slot(bank, owner, depth) for depth in range(4))
            for owner in range(2)), reads=tuple(Bundle(valid=signal(bank, f'io_read_{owner}_valid'),
            ready=signal(bank, f'io_read_{owner}_ready')) for owner in range(2))) for bank in range(4))
        super().__init__(PortBinding(dut.clock, Bundle(banks=banks), f'tage.table{table}_shadow'), decoder=self.decode)

    @staticmethod
    def decode(sample):
        return {'banks': tuple({'shadow': tuple(tuple({field: getattr(slot, field).as_int()
            for field in SLOT_FIELDS} for slot in row) for row in bank.shadow),
            'reads': tuple({'valid': port.valid.as_int(), 'ready': port.ready.as_int()}
                for port in bank.reads)} for bank in sample.banks)}
