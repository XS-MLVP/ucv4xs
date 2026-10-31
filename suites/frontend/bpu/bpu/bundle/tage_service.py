"""Read-only SRAM service boundary, addressed by independently owned providers."""
from toffee import Bundle,ReadyValid,Role

from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal,memory_signal_names


def service_binding(agent,*,table,bank,include_retention=False):
    anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    base=f'tage.tables_{table}.'
    writes=[]
    for way in range(2):
        port=base+f'tage_entry_write_buffer_bank{bank}.io_read_{way}_'
        bits=Bundle(row=signal(port+'bits_setIdx'),valid=signal(port+'bits_entry_valid'),
            tag=signal(port+'bits_entry_tag'),counter=signal(port+'bits_entry_takenCtr_value'))
        writes.append(ReadyValid(clock=agent.dut.clock,valid=signal(port+'valid'),ready=signal(port+'ready'),
            bits=bits,role=Role.MONITOR,name=f'bpu.tage.service.{table}.{bank}.{way}'))
    fields={}
    if include_retention:
        buffer=base+f'tage_entry_write_buffer_bank{bank}.'
        fields['dirty']=tuple(tuple(signal(buffer+f'dirty_{way}_{rank}') for rank in range(4)) for way in range(2))
        fields['incoming']=tuple(Bundle(valid=signal(buffer+f'io_write_{way}_valid'),bits=Bundle(
            row=signal(buffer+f'io_write_{way}_bits_setIdx'),
            valid=signal(buffer+f'io_write_{way}_bits_entry_valid'),
            tag=signal(buffer+f'io_write_{way}_bits_entry_tag'),
            counter=signal(buffer+f'io_write_{way}_bits_entry_takenCtr_value'))) for way in range(2))
    state=Bundle(**fields,reset=signal('reset'),
        reads=tuple(Bundle(valid=signal(base+f'io_readReq_{port}_valid'),
            mask=signal(base+f'io_readReq_{port}_bits_bankMask')) for port in range(2)),
        training=Bundle(valid=signal('io_fromFtq_train_valid'),ready=signal('io_fromFtq_train_ready')),
        prediction=Bundle(valid=signal('io_toFtq_prediction_valid'),ready=signal('io_toFtq_prediction_ready'),
            pc=signal('io_toFtq_prediction_bits_startPc_addr')),
        writes=tuple(Bundle(valid=port.valid,ready=port.ready,bits=port.bits) for port in writes))
    return PortBinding(agent.dut.clock,state,'bpu.tage.read-priority-service'),tuple(writes)


def useful_service_binding(agent,*,table,bank,include_retention=False):
    """Useful learning has a distinct service channel from entry-counter writes."""
    if include_retention:raise ValueError('entry retention is not a useful service field')
    anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    base=f'tage.tables_{table}.'
    writes,incoming,queues,flushes=[],[],[],[]
    for way in range(2):
        port=base+f'tage_useful_write_buffer_bank{bank}_way{way}.'
        bits=lambda side:Bundle(row=signal(port+f'io_{side}_bits_setIdx'),
            value=signal(port+f'io_{side}_bits_usefulCtr_value'))
        writes.append(ReadyValid(clock=agent.dut.clock,valid=signal(port+'io_deq_valid'),
            ready=signal(port+'io_deq_ready'),bits=bits('deq'),role=Role.MONITOR,
            name=f'bpu.tage.useful-service.{table}.{bank}.{way}'))
        incoming.append(Bundle(valid=signal(port+'io_enq_valid'),ready=signal(port+'io_enq_ready'),bits=bits('enq')))
        queues.append(Bundle(enqueue=signal(port+'enq_ptr_value'),dequeue=signal(port+'deq_ptr_value'),
            full=signal(port+'maybe_full')))
        flushes.append(signal(port+'io_flush'))
    state=Bundle(reset=signal('reset'),
        reads=tuple(Bundle(valid=signal(base+f'io_readReq_{port}_valid'),
            mask=signal(base+f'io_readReq_{port}_bits_bankMask')) for port in range(2)),
        training=Bundle(valid=signal('io_fromFtq_train_valid'),ready=signal('io_fromFtq_train_ready')),
        prediction=Bundle(valid=signal('io_toFtq_prediction_valid'),ready=signal('io_toFtq_prediction_ready'),
            pc=signal('io_toFtq_prediction_bits_startPc_addr')),
        writes=tuple(Bundle(valid=port.valid,ready=port.ready,bits=port.bits) for port in writes),
        incoming=tuple(incoming),queues=tuple(queues),flushes=tuple(flushes))
    return PortBinding(agent.dut.clock,state,'bpu.tage.useful-read-priority-service'),tuple(writes)
