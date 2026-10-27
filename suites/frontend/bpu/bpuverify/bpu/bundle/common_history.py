"""Read-only CommonHR direction state and public backend recovery boundary."""
from bpuverify.common.model.configuration import *

from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal,memory_signal_names


def common_history_binding(agent,*,observe_state=True):
    anchor,=[n for n in memory_signal_names(agent.dut) if n.endswith('.commonHR.commonHR_ghr')]
    prefix=anchor.removeprefix('TOP.').removesuffix('commonHR.commonHR_ghr')
    signal=lambda field:memory_signal(agent.dut,prefix+field)
    base='io_fromFtq_redirect_bits_';meta=base+'meta_commonHRMeta_'
    state=dict(state=Bundle(valid=signal('commonHR.commonHR_valid'),ghr=signal('commonHR.commonHR_ghr'),bw=signal('commonHR.commonHR_bw'))) if observe_state else {}
    return PortBinding(agent.dut.clock,Bundle(**state,reset=signal('reset'),
        redirect=Bundle(valid=signal('io_fromFtq_redirect_valid'),pc=signal(base+'cfiPc_addr'),
            target=signal(base+'target_addr'),taken=signal(base+'taken'),kind=signal(base+'attribute_branchType'),
            meta=Bundle(ghr=signal(meta+'ghr'),bw=signal(meta+'bw'),
                hits=tuple(signal(meta+f'hitMask_{i}') for i in range(RESULT_SLOTS)),
                kinds=tuple(signal(meta+f'attribute_{i}_branchType') for i in range(RESULT_SLOTS)),
                positions=tuple(signal(meta+f'position_{i}') for i in range(RESULT_SLOTS))))),'bpu.owned-common-direction-history')
