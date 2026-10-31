"""Compiled memory-direct view; normal writes and maintenance share no driver."""
from suites.frontend.bpu.models.configuration import *

from toffee import Bundle
from suites.frontend.bpu.runtime.memory_direct import memory_signal,memory_signal_names
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor
from suites.frontend.bpu.bpu.bundle.values import _plain
from suites.frontend.bpu.bpu.monitor.tage.selector import TageSelectorMonitor


class TageAgingMonitor(CycleMonitor):
    def __init__(self,agent):
        base=TageSelectorMonitor(agent)
        anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.tage.useAltOnNaVec_0_value')]
        prefix=anchor.removeprefix('TOP.').removesuffix('useAltOnNaVec_0_value')
        signal=lambda leaf:memory_signal(agent.dut,prefix+leaf)
        def table_view(t):
            leaf=lambda name:signal(f'tables_{t}.{name}')
            def bank_view(b):
                return Bundle(busy=leaf(f'usefulResetInFlightMask_{b}'),index=leaf(f'usefulResetSetIdx_{b}'),
                    ports=tuple(Bundle(valid=leaf(f'tage_useful_sram_bank{b}_way{w}.io_w_req_valid'),
                        ready=leaf(f'tage_useful_sram_bank{b}_way{w}.io_w_req_ready'),
                        address=leaf(f'tage_useful_sram_bank{b}_way{w}.io_w_req_bits_setIdx'),
                        data=leaf(f'tage_useful_sram_bank{b}_way{w}.io_w_req_bits_data_0_value'),
                        enq=leaf(f'tage_useful_write_buffer_bank{b}_way{w}.io_enq_valid'),
                        flush=leaf(f'tage_useful_write_buffer_bank{b}_way{w}.io_flush')) for w in range(2)))
            return Bundle(busy=leaf('io_usefulResetInFlight'),start=leaf('io_usefulResetStart'),
                banks=tuple(bank_view(b) for b in range(4)),
                staged_valid=leaf('writeReqValid'),staged_useful=tuple(leaf(f'writeReq_writeUsefulEn_{w}') for w in range(2)),
                write=Bundle(valid=leaf('io_writeReq_valid'),index=leaf('io_writeReq_bits_setIdx'),
                    bank=leaf('io_writeReq_bits_bankMask'),way=leaf('io_writeReq_bits_wayMask'),
                    entries=tuple(Bundle(entry_en=leaf(f'io_writeReq_bits_writeEntryEn_{w}'),
                        useful_en=leaf(f'io_writeReq_bits_writeUsefulEn_{w}'),taken=leaf(f'io_writeReq_bits_actualTakenMask_{w}'),
                        valid=leaf(f'io_writeReq_bits_entries_{w}_valid'),tag=leaf(f'io_writeReq_bits_entries_{w}_tag'),
                        counter=leaf(f'io_writeReq_bits_entries_{w}_takenCtr_value'),
                        useful=leaf(f'io_writeReq_bits_usefulCtrs_{w}_value')) for w in range(2))))
        age=Bundle(counter=signal('usefulResetCtr_value'),busy=signal('usefulResetInFlight'),
            start=signal('t3_usefulResetStart'),need=signal('t3_needAllocate'),can=signal('t3_canAllocateTableMask'),
            allocate=signal('t3_allocate'),table=signal('t3_allocateTableOH'),way=signal('t3_allocateWayOH'),
            random=signal('t3_allocateTableRandomMask'),tables=tuple(table_view(t) for t in range(TAGE_TABLES)),
            bank=signal('t2_bankMask'),sets=tuple(signal(f't2_setIdx_{t}') for t in range(TAGE_TABLES)),
            public_useful=tuple(signal(f'io_meta_entries_{s}_providerUsefulCtr_value') for s in range(RESULT_SLOTS)))
        super().__init__(PortBinding(agent.dut.clock,Bundle(selector=base.binding.bits,age=age),
            'bpu.tage.useful_aging_events'),decoder=_plain)
