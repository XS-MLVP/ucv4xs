"""Read-only actual hit ownership; no raw tag probing or RTL-state writes."""
from toffee import Bundle
from bpuverify.bpu.bundle.tage_service import service_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def partial_residency_binding(agent, *, table, bank, include_retention=False, include_hit_ranks=False):
    if not include_retention:
        raise ValueError('partial residency requires actual dirty and proposal observations')
    binding, ports = service_binding(agent, table=table, bank=bank, include_retention=True)
    anchor, = [n for n in memory_signal_names(agent.dut) if n.endswith('.tage.io_enable')]
    root = anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    base = root + f'tage.tables_{table}.tage_entry_write_buffer_bank{bank}.'
    signal = lambda field: memory_signal(agent.dut, base + field)
    # Trace-derived aliases split the two owner-0 low-rank matches into one
    # OR term. All terms below exist in the pinned memory-direct layout.
    hits = (Bundle(owner0=(signal('_hitRowsVec_T'), signal('hitMask_0_2'), signal('hitMask_0_3')),
                   owner1=signal('rowIdx')),
            Bundle(owner0=(signal('_hitRowsVec_T_6'), signal('hitMask_1_0_2'), signal('hitMask_1_0_3')),
                   owner1=signal('rowIdx_1')))
    fields = dict(state=binding.bits, owner_hits=hits)
    if include_hit_ranks:
        fields['hit_ranks'] = ((signal('hitRowIdxVec_0'), signal('hitRowIdxVec_1')),
                               (signal('hitRowIdxVec_1_0'), signal('hitRowIdxVec_1_1')))
    return PortBinding(binding.clock, Bundle(**fields),
                       'bpu.tage.partial-residency'), ports
