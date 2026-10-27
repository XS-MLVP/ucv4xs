"""bpuverify.bpu.monitor.sc.common_state components."""

from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.common.env.memory_direct import memory_signal_names
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.common.monitor.cycle import CycleMonitor


class CommonStateMonitor(CycleMonitor):
    def __init__(self, agent):
        dut = agent.dut
        anchor, = [name for name in memory_signal_names(dut)
                   if name.endswith('.commonHR.commonHR_ghr')]
        prefix = anchor.split('.', 1)[1].removesuffix('commonHR_ghr')

        def signal(leaf):
            value = memory_signal(dut, prefix + leaf)
            if value is None:
                raise RuntimeError(f'Missing read-only CommonHR state input: {prefix + leaf}')
            return value

        def vector(base):
            return tuple(signal(f'{base}_{index}') for index in range(4))

        s2 = Bundle(pc=signal('io_s2Update_startPc_addr'), positions=vector('io_s2Update_positions'),
            targets=tuple(signal(f'io_s2Update_targets_{i}_addr') for i in range(4)),
            hits=vector('io_s2Update_condHitMask'))
        s3 = Bundle(pc=signal('io_s3Update_startPc_addr'), taken=signal('io_s3Update_prediction_taken'),
            position=signal('io_s3Update_prediction_cfiPosition'), target=signal('io_s3Update_prediction_target_addr'),
            branch_type=signal('io_s3Update_prediction_attribute_branchType'),
            first=vector('io_s3Update_firstTakenBranchOH'))
        redirect = Bundle(valid=signal('io_redirect_valid'), taken=signal('io_redirect_taken'),
            cfi_pc=signal('io_redirect_cfiPc_addr'), target=signal('io_redirect_target_addr'),
            branch_type=signal('io_redirect_attribute_branchType'),
            meta=Bundle(ghr=signal('io_redirect_meta_ghr'), bw=signal('io_redirect_meta_bw'),
                hits=vector('io_redirect_meta_hitMask'), positions=vector('io_redirect_meta_position')))
        super().__init__(PortBinding(dut.clock, Bundle(reset=dut.reset,
            fire2=signal('io_stageCtrl_s2_fire'), fire3=signal('io_stageCtrl_s3_fire'),
            state=Bundle(valid=signal('commonHR_valid'), ghr=signal('commonHR_ghr'), bw=signal('commonHR_bw')),
            s2=s2, s3=s3, redirect=redirect), 'bpu.common_history_state'), decoder=_plain)
