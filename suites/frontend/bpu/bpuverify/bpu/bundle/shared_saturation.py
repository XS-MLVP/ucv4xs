"""Read-only current logical records beside the existing service binding."""
from toffee import Bundle
from bpuverify.bpu.bundle.tage_service import service_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def binding(agent,*,table,bank,include_retention=False):
    if not include_retention:raise ValueError('shared saturation requires current retained records')
    state,ports=service_binding(agent,table=table,bank=bank,include_retention=True)
    anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    root=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    root+=f'tage.tables_{table}.tage_entry_write_buffer_bank{bank}.'
    signal=lambda suffix:memory_signal(agent.dut,root+suffix)
    records=tuple(tuple(Bundle(shadow=signal(f'shadowValid_{owner}_{rank}'),
        row=signal(f'entries_{owner}_{rank}_setIdx'),valid=signal(f'entries_{owner}_{rank}_entry_valid'),
        tag=signal(f'entries_{owner}_{rank}_entry_tag'),counter=signal(f'entries_{owner}_{rank}_entry_takenCtr_value'))
        for rank in range(4)) for owner in range(2))
    return PortBinding(state.clock,Bundle(state=state.bits,records=records),'bpu.tage.shared-saturation'),ports
