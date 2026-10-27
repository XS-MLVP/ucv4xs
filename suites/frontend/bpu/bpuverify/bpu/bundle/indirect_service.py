"""Read-only full ITTAGE entry service and offered-learning boundaries."""
from toffee import Bundle,ReadyValid,Role
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def indirect_service_binding(agent,*,table,bank,include_retention=False):
    anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.ittage.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('ittage.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    base=f'ittage.tables_{table}.';buffer=base+f'ittage_write_buffer_bank{bank}.'
    def bits(port,*,incoming=False):
        return Bundle(**{name:signal(buffer+port+field) for name,field in (
            ('row','setIdx'),('valid','entry_valid'),('tag','entry_tag'),('confidence','entry_confidenceCnt_value'),
            ('useful','entry_usefulCnt_value'),('offset','entry_targetOffset_offset_addr'),
            ('pointer','entry_targetOffset_pointer'),('pc_region','entry_targetOffset_usePcRegion'),('mask','bitmask'))
            if not (incoming and name=='valid')})
    port=ReadyValid(clock=agent.dut.clock,valid=signal(buffer+'io_read_0_valid'),ready=signal(buffer+'io_read_0_ready'),
        bits=bits('io_read_0_bits_'),role=Role.MONITOR,name=f'bpu.ittage.service.{table}.{bank}')
    fields={}
    if include_retention:fields['dirty']=tuple(signal(buffer+f'dirty_0_{rank}') for rank in range(4))
    state=Bundle(**fields,reset=signal('reset'),maintenance=signal(base+'needReset'),
        read=Bundle(valid=signal(base+'io_req_valid'),ready=signal(base+'io_req_ready'),pc=signal(base+'io_req_bits_startPc_addr')),
        # entry.valid is constant-folded before this input boundary. Do not
        # fabricate an XData for it; the actual service output includes it.
        incoming=Bundle(valid=signal(buffer+'io_write_0_valid'),bits=bits('io_write_0_bits_',incoming=True)),
        write=Bundle(valid=port.valid,ready=port.ready,bits=port.bits),
        training=Bundle(valid=signal('io_fromFtq_train_valid'),ready=signal('io_fromFtq_train_ready')),
        prediction=Bundle(valid=signal('io_toFtq_prediction_valid'),ready=signal('io_toFtq_prediction_ready'),
            pc=signal('io_toFtq_prediction_bits_startPc_addr')))
    return PortBinding(agent.dut.clock,state,'bpu.ittage.read-priority-service'),(port,)
