"""Static, read-only MainBTB response ports through the memory-direct SDK."""
from toffee import Bundle

from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def main_replacement_binding(agent):
    anchor,=[name for name in memory_signal_names(agent.dut) if name.endswith('.tage.io_enable')]
    prefix=anchor.removeprefix('TOP.').removesuffix('tage.io_enable')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    entries=[]
    for slot in range(4):
        base=f'mbtb.io_result_{slot}_'
        entries.append(Bundle(valid=signal(base+'valid'),
            position=signal(base+'bits_cfiPosition'),target=signal(base+'bits_target_addr'),
            kind=signal(base+'bits_attribute_branchType'),action=signal(base+'bits_attribute_rasAction'),
            taken=signal(base+'bits_taken'),
            counter=signal(f'mbtb.io_meta_entries_{slot//2}_{slot%2}_counter_value')))
    return PortBinding(agent.dut.clock,Bundle(reset=signal('reset'),valid=signal('s2_valid'),
        pc=signal('s2_startPc_dup_0_addr'),entries=tuple(entries)),'bpu.main-replacement-response')
