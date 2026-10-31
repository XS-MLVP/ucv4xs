"""Read-only memory-direct iteration cursor and exact public recovery input."""
from toffee import Bundle

from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.runtime.memory_direct import memory_signal, memory_signal_names


def loop_iteration_binding(agent, *, observe_state=True):
    if not observe_state:
        raise ValueError('iteration timing checks require the memory-direct state boundary')
    anchor, = [n for n in memory_signal_names(agent.dut) if n.endswith('.commonHR.commonHR_ghr')]
    prefix = anchor.removeprefix('TOP.').removesuffix('commonHR.commonHR_ghr')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    base = 'io_fromFtq_redirect_bits_'
    return PortBinding(agent.dut.clock, Bundle(reset=signal('reset'),
        state=signal('commonHR.imli'), lookup=signal('commonHR.io_s0_imli'),
        stages=tuple(signal(f'commonHR.s{i}_imli') for i in (1, 2, 3)),
        repairs=tuple(signal(f's{i}_override') for i in (2, 3)),
        redirect=Bundle(valid=signal('io_fromFtq_redirect_valid'),
            pc=signal(base+'cfiPc_addr'), target=signal(base+'target_addr'),
            taken=signal(base+'taken'), kind=signal(base+'attribute_branchType'),
            count=signal(base+'meta_commonHRMeta_imli'))), 'bpu.owned-loop-iteration')
