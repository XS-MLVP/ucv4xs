"""suites.frontend.bpu.bpu.monitor.sc.common_routes components."""
from suites.frontend.bpu.models.configuration import *


from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.bpu.bundle.values import _plain
from suites.frontend.bpu.monitors.cycle import CycleMonitor


class CommonHistoryMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        anchor, = [name for name in memory_signal_names(dut)
                   if name.endswith('.sc.pathTable_0.writeBuffer_0.shadowValid_0_0')]
        prefix = anchor.split('.', 1)[1].split('pathTable_0.', 1)[0]

        def signal(leaf):
            value = memory_signal(dut, prefix + leaf)
            if value is None:
                raise RuntimeError(f'Missing read-only CommonHR route signal: {prefix + leaf}')
            return value

        reads = {table: Bundle(valid=signal(table + '.io_predictReadReq_valid'),
            set_index=signal(table + '.io_predictReadReq_bits_setIdx'),
            bank_mask=signal(table + '.io_predictReadReq_bits_bankMask'))
            for table in ('globalTable_0', 'globalTable_1', 'bwTable_0', 'bwTable_1')}
        super().__init__(PortBinding(dut.clock, Bundle(reset=dut.reset,
            enable=signal('io_enable'), stage_fire=signal('io_stageCtrl_s0_fire'), fire=signal('s0_fire'),
            pc=signal('io_startPc_addr'), common=Bundle(valid=signal('io_commonHR_valid'),
                ghr=signal('io_commonHR_ghr'), bw=signal('io_commonHR_bw')),
            reads=Bundle(**reads)), 'bpu.sc.common_history_prediction_routes'), decoder=_plain)
