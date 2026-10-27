"""Static read-only confidence and auxiliary no-loss observation ports."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.bundle.partial_residency import partial_residency_binding
from bpuverify.bpu.bundle.main_service import main_service_binding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names
from bpuverify.bpu.model.direction_sources import HISTORY_PORTS


def confidence_boundary_binding(agent,*,table,bank,include_retention=False):
    binding,ports=partial_residency_binding(agent,table=table,bank=bank,
        include_retention=include_retention,include_hit_ranks=True)
    main=tuple(main_service_binding(agent,alignment=a,bank=0)[0].bits for a in range(2))
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.phr.phrPtr_value')]
    prefix=anchor.removeprefix('TOP.').removesuffix('phrPtr_value')
    train_folds=tuple(memory_signal(agent.dut,prefix+f'io_trainFoldedPhr_hist_{i}_foldedHist') for i in HISTORY_PORTS)
    return PortBinding(binding.clock,Bundle(state=binding.bits.state,owner_hits=binding.bits.owner_hits,
        hit_ranks=binding.bits.hit_ranks,main=main,train_folds=train_folds),'bpu.tage.confidence-boundary'),ports
