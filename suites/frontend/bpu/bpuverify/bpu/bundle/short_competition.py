"""Static shared SRAM and complete long-write snapshots, read only."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.bundle.history_working_set import short_storage_binding
from bpuverify.utage.monitor.shadow import UtageShadowMonitor


def competition_binding(agent,program,**options):
    binding,layout=short_storage_binding(agent,program.storage_paths,**options)
    _,_,long_shadow=UtageShadowMonitor._bind(agent,1)
    return PortBinding(binding.clock,Bundle(inputs=binding.bits.inputs,
        observed=Bundle(**dict(binding.bits.observed),
            competition_long=Bundle(cells=long_shadow.bits.cells,enq=long_shadow.bits.enq))),
        'bpu.short-branch-competition'),layout
