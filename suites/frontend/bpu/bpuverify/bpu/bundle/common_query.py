"""Existing read-only memory-direct lookup ports and public history metadata."""
from toffee import Bundle
from bpuverify.bpu.bundle.loop_iteration import loop_iteration_binding
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal, memory_signal_names


def common_query_binding(agent, *, observe_state=True):
    anchor, = [name for name in memory_signal_names(agent.dut) if name.endswith('.commonHR.commonHR_ghr')]
    prefix = anchor.removeprefix('TOP.').removesuffix('commonHR.commonHR_ghr')
    signal = lambda field: memory_signal(agent.dut, prefix + field)
    history = lambda base: Bundle(**{field: signal(base + field) for field in ('valid', 'ghr', 'bw')})
    return PortBinding(agent.dut.clock, Bundle(
        iteration=loop_iteration_binding(agent, observe_state=observe_state).bits,
        state=history('commonHR.commonHR_'), lookup=history('commonHR.io_s0_commonHR_'),
        published=Bundle(valid=signal('io_toFtq_meta_valid'),
            common=history('io_toFtq_meta_bits_resolveMeta_commonHR_'),
            loop=signal('io_toFtq_meta_bits_resolveMeta_commonHR_imli'))), 'bpu.owned-query-history')
