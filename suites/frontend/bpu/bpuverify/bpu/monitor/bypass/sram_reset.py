"""Observe committed RTL reset, never the pending Rise-written input cache."""
from bpuverify.common.env.memory_direct import memory_signal
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding

from bpuverify.bpu.monitor.bypass import sram_base as _v5


class SramMonitor(_v5.SramMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        tables = []
        for prefix, table in zip(self.prefixes, self.binding.bits.sram, strict=True):
            prefix = prefix.removesuffix('wbuffer.')
            def signal(name, prefix=prefix):
                value = memory_signal(agent.dut, prefix + name)
                if value is None:
                    raise RuntimeError(f'committed SRAM leaf unavailable: {prefix + name}')
                return value
            tables.append(Bundle(**dict(table), reset=signal('reset'),
                raw_entry_valid=signal('sramRealReadEntry_valid')))
        old = self.binding.bits
        self.binding = PortBinding(agent.dut.clock,
            Bundle(reset=tables[0].reset, requested_reset=old.reset,
                tables=old.tables, sram=tuple(tables)), 'bpu.integrated_microtage_sram')
