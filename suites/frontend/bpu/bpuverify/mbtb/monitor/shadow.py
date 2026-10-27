"""Passive MainBTB entry shadow snapshots, including both buffer depths.

This observes retained ownership only. It neither chooses expected owners nor
drives internal state; architectural predictions still use the public monitor.
"""
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.mbtb.monitor.entry import ENTRY_FIELDS
from bpuverify.common.monitor.cycle import CycleMonitor


class MbtbEntryShadowMonitor(CycleMonitor):
    def __init__(self, dut):
        names = tuple(memory_signal_names(dut))

        def signal(align, bank, name):
            suffix = f'.MainBtb.alignBanks_{align}.internalBanks_{bank}.entryWriteBuffer.{name}'
            matches = [value for value in names if value.endswith(suffix)]
            if len(matches) != 1:
                raise RuntimeError(f'MainBTB shadow signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.', 1)[1])

        def slot(align, bank, owner, depth):
            values = dict(valid=signal(align, bank, f'shadowValid_{owner}_{depth}'),
                          dirty=signal(align, bank, f'dirty_{owner}_{depth}'))
            values.update({key: signal(align, bank, f'entries_{owner}_{depth}_{name}')
                           for key, name in ENTRY_FIELDS})
            return Bundle(**values)

        banks = tuple(tuple(tuple(tuple(slot(align, bank, owner, depth) for depth in range(2))
                                  for owner in range(2)) for bank in range(2)) for align in range(2))
        super().__init__(PortBinding(dut.clock, Bundle(banks=banks), 'mbtb.entry_shadow'), decoder=self.decode)

    @staticmethod
    def decode(sample):
        fields = ('valid', 'dirty') + tuple(key for key, _ in ENTRY_FIELDS)
        return {'banks': tuple(tuple(tuple(tuple({key: getattr(slot, key).as_int() for key in fields}
                                                 for slot in depths) for depths in owners)
                                    for owners in row) for row in sample.banks)}
