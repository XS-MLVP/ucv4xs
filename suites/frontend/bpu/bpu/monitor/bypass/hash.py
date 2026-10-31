"""Extend frozen SRAM Bundle with read-only parent hash and priority inputs."""
from suites.frontend.bpu.runtime.memory_direct import memory_signal
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding

from suites.frontend.bpu.bpu.monitor.bypass import sram as _v14


class SramMonitor(_v14.SramMonitor):
    def __init__(self, agent):
        super().__init__(agent)
        prefix = self.prefixes[0].removesuffix('MicroTageTable.wbuffer.')
        def signal(name):
            value = memory_signal(agent.dut, prefix + name)
            if value is None:
                raise RuntimeError(f'MicroTAGE hash leaf unavailable: {prefix + name}')
            return value
        phr_prefix = prefix.removesuffix('utage.') + 'phr.'
        def phr(name):
            value = memory_signal(agent.dut, phr_prefix + name)
            if value is None:
                raise RuntimeError(f'PHR priority leaf unavailable: {phr_prefix + name}')
            return value
        hash_inputs = Bundle(pc=signal('io_startPc_addr'), new_pc=signal('io_newStartPc_addr'),
            normal_folds=tuple(signal(f'io_normalPathHist_hist_{i}_foldedHist') for i in (2, 9)),
            s1_folds=tuple(signal(f'io_s1PathHist_hist_{i}_foldedHist') for i in (1, 2, 7, 8)),
            redirect_valid=phr('io_train_redirect_valid'),
            redirect_low=phr('io_train_redirect_bits_meta_phr_phrLowBits'),
            s2_override=phr('io_train_s2_overrideValid'), s3_override=phr('io_train_s3_overrideValid'))
        old = self.binding.bits
        self.binding = PortBinding(agent.dut.clock, Bundle(**dict(old), hash_inputs=hash_inputs),
            'bpu.integrated_microtage_sram_nonzero_hash')
