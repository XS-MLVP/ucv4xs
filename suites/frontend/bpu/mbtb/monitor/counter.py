"""Passive counter requests, writebacks and occupancy across all physical banks."""
from suites.frontend.bpu.models.configuration import *
from suites.frontend.bpu.runtime.memory_direct import memory_signal
from suites.frontend.bpu.runtime.memory_direct import memory_signal_names
from dataclasses import dataclass
from dataclasses import field

from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.monitors.cycle import CycleMonitor


QUEUE_FIELDS = (
    ('enq_valid','io_enq_valid'),('enq_ready','io_enq_ready'),
    ('deq_valid','io_deq_valid'),('deq_ready','io_deq_ready'),
    ('enq_set','io_enq_bits_setIdx'),('enq_way','io_enq_bits_wayMask'),
    ('deq_set','io_deq_bits_setIdx'),('deq_way','io_deq_bits_wayMask'),
    ('enq_ptr','enq_ptr_value'),('deq_ptr','deq_ptr_value'),
    ('empty','empty'),('maybe_full','maybe_full'),('do_enq','do_enq'),
)


@dataclass
class MbtbCounterActivityTrace:
    feedback: list = field(default_factory=list)
    frames: list = field(default_factory=list)


class MbtbCounterActivityMonitor(CycleMonitor):
    def __init__(self,dut):
        names = tuple(memory_signal_names(dut))

        def signal(align,bank,field):
            suffix = f'.MainBtb.alignBanks_{align}.internalBanks_{bank}.counterWriteBuffer.{field}'
            matches = [name for name in names if name.endswith(suffix)]
            if len(matches)!=1:
                raise RuntimeError(f'MainBTB counter signal {suffix} needs one memory-direct binding; found {len(matches)}: {matches}')
            return memory_signal(dut, matches[0].split('.',1)[1])

        def queue(align,bank):
            fields = {key:signal(align,bank,name) for key,name in QUEUE_FIELDS}
            for port in ('enq','deq'):
                fields[port+'_counters'] = tuple(signal(align,bank,f'io_{port}_bits_counters_{way}_value')
                                               for way in range(MAIN_WAYS))
            return Bundle(**fields)

        queues = tuple(tuple(queue(align,bank) for bank in range(MAIN_BANKS)) for align in range(2))
        super().__init__(PortBinding(dut.clock,Bundle(queues=queues),'mbtb.counter_activity'),decoder=self.decode)

    @staticmethod
    def decode(sample):
        def queue(value):
            fields = {key:getattr(value,key).as_int() for key,name in QUEUE_FIELDS}
            fields.update({port+'_counters':tuple(word.as_int() for word in getattr(value,port+'_counters'))
                           for port in ('enq','deq')})
            return fields
        return {'queues':tuple(tuple(queue(value) for value in row) for row in sample.queues)}
