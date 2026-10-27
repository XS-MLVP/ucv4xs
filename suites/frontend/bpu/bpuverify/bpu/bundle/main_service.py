"""Read-only complete MainBTB entry service and separately masked directions."""
from bpuverify.common.model.configuration import *
from toffee import Bundle,ReadyValid,Role
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def main_service_binding(agent,*,alignment,bank):
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.mbtb.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('mbtb.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    base=f'mbtb.alignBanks_{alignment}.internalBanks_{bank}.'
    def entry(side,way):
        port=base+f'entryWriteBuffer.io_{side}_{way}_bits_'
        return Bundle(**{name:signal(port+field) for name,field in (
            ('row','setIdx'),('tag','entry_tag'),('position','entry_position'),('kind','entry_attribute_branchType'),
            ('action','entry_attribute_rasAction'),('carry','entry_targetCarry_value'),('offset','entry_targetLowerBits'))})
    def counters(side):
        port=base+f'counterWriteBuffer.io_{side}_bits_'
        return Bundle(row=signal(port+'setIdx'),mask=signal(port+'wayMask'),
            counters=tuple(signal(port+f'counters_{way}_value') for way in range(MAIN_WAYS)))
    ports=[]
    for way in range(MAIN_WAYS):
        port=base+f'entryWriteBuffer.io_read_{way}_'
        ports.append(ReadyValid(clock=agent.dut.clock,valid=signal(port+'valid'),ready=signal(port+'ready'),
            bits=entry('read',way),role=Role.MONITOR,name=f'bpu.main.entry-service.{alignment}.{bank}.{way}'))
    ports.append(ReadyValid(clock=agent.dut.clock,valid=signal(base+'counterWriteBuffer.io_deq_valid'),
        ready=signal(base+'counterWriteBuffer.io_deq_ready'),bits=counters('deq'),role=Role.MONITOR,
        name=f'bpu.main.counter-service.{alignment}.{bank}'))
    state=Bundle(reset=signal('reset'),initialized=signal(base+'io_sramResetDone'),
        read=Bundle(valid=signal(base+'io_read_req_valid'),row=signal(base+'io_read_req_bits_setIdx')),
        training=Bundle(valid=signal('io_fromFtq_train_valid'),ready=signal('io_fromFtq_train_ready')),
        prediction=Bundle(valid=signal('io_toFtq_prediction_valid'),ready=signal('io_toFtq_prediction_ready'),
            pc=signal('io_toFtq_prediction_bits_startPc_addr')),
        writes=tuple(Bundle(valid=p.valid,ready=p.ready,bits=p.bits) for p in ports),
        incoming=tuple(Bundle(valid=signal(base+f'entryWriteBuffer.io_write_{way}_valid'),bits=entry('write',way))
            for way in range(MAIN_WAYS)),
        direction=Bundle(valid=signal(base+'counterWriteBuffer.io_enq_valid'),
            ready=signal(base+'counterWriteBuffer.io_enq_ready'),bits=counters('enq')),
        dirty=tuple(tuple(signal(base+f'entryWriteBuffer.dirty_{way}_{rank}') for rank in range(MAIN_RETAINED)) for way in range(MAIN_WAYS)),
        queue=Bundle(enqueue=signal(base+'counterWriteBuffer.enq_ptr_value'),dequeue=signal(base+'counterWriteBuffer.deq_ptr_value'),
            full=signal(base+'counterWriteBuffer.maybe_full')))
    return PortBinding(agent.dut.clock,state,'bpu.main.read-priority-service'),tuple(ports)
