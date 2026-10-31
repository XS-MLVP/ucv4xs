"""Static read-only complete retained versions and actual admission surfaces."""
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal,memory_signal_names
from suites.frontend.bpu.bpu.bundle.tage_service import service_binding
from suites.frontend.bpu.bpu.bundle.main_service import main_service_binding
from suites.frontend.bpu.bpu.model.direction_sources import HISTORY_PORTS


def retouch_replacement_binding(agent,*,table,bank,include_retention=False):
    binding,ports=service_binding(agent,table=table,bank=bank,include_retention=include_retention)
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.tage.io_enable')]
    root=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal=lambda path:memory_signal(agent.dut,root+path)
    base=f'tage.tables_{table}.tage_entry_write_buffer_bank{bank}.'
    retained=tuple(tuple(Bundle(shadow=signal(base+f'shadowValid_{owner}_{rank}'),
        row=signal(base+f'entries_{owner}_{rank}_setIdx'),valid=signal(base+f'entries_{owner}_{rank}_entry_valid'),
        tag=signal(base+f'entries_{owner}_{rank}_entry_tag'),
        counter=signal(base+f'entries_{owner}_{rank}_entry_takenCtr_value')) for rank in range(4)) for owner in range(2))
    main=[]
    for align in range(2):
        child,_=main_service_binding(agent,alignment=align,bank=0)
        main.append(Bundle(read=child.bits.read,direction=child.bits.direction))
    train_folds=tuple(signal(f'phr.io_trainFoldedPhr_hist_{i}_foldedHist') for i in HISTORY_PORTS)
    return PortBinding(binding.clock,Bundle(state=binding.bits,retained=retained,main=tuple(main),
        train_folds=train_folds),'bpu.tage.retouch-replacement'),ports
