"""Static memory-direct PLRU state extends the inherited lossless SC monitor."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.bpu.model.sc.model import NAMES
from bpuverify.bpu.monitor.sc.used import UsedScMonitor

class FullScMonitor(UsedScMonitor):

    def __init__(self, agent):
        super().__init__(agent)
        base = self.binding
        state = {}
        for name in NAMES:
            path = self.paths[name] + 'state_reg'
            value = memory_signal(agent.dut, path)
            if value is None:
                raise RuntimeError(f'Missing static SC replacement state: {path}')
            state[name] = value
        bits = base.bits
        self.binding = PortBinding(base.clock, Bundle(buffers=bits.buffers, t0=bits.t0, training=bits.training, prediction=bits.prediction, used_pipeline=bits.used_pipeline, replacement=Bundle(**state)), 'bpu.sc.full_capacity_and_used')
