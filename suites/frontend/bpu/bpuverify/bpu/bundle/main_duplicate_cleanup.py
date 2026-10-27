"""Read-only parent operations explain the two buffer inputs."""
from toffee import Bundle
from bpuverify.bpu.bundle.main_service import main_service_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def binding(agent):
    base,ports=main_service_binding(agent,alignment=0,bank=0)
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.mbtb.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('io_enable')+'alignBanks_0.internalBanks_0.'
    signal=lambda name:memory_signal(agent.dut,prefix+name)
    parent=Bundle(cleanup=Bundle(valid=signal('io_flush_req_valid'),row=signal('io_flush_req_bits_setIdx'),
        mask=signal('io_flush_req_bits_wayMask')),
        learning=Bundle(valid=signal('io_writeEntry_req_valid'),row=signal('io_writeEntry_req_bits_setIdx'),
            mask=signal('io_writeEntry_req_bits_wayMask')))
    return PortBinding(base.clock,Bundle(state=base.bits,parent=parent),'bpu.main.duplicate-cleanup-parent'),ports
