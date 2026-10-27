"""Static memory-direct extension of the admitted Bundle/@on SC monitor."""
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.env.memory_direct import memory_signal
from bpuverify.bpu.monitor.sc.observer import ScMonitor

def pipeline_leaves():
    return tuple([f'scThreshold_{way}_value' for way in range(4)] + [f't1_writeThresVec_{way}_value' for way in range(4)] + [f'{name}_{slot}' for name in ('t0_writeValidVec', 't1_writeValidVecReg', 't1_writeValidVec') for slot in range(8)] + ['t1_fire', 't1_writeValid', 't2_writeValid'])

class UsedScMonitor(ScMonitor):
    """Inherited lossless rising/DriveStable subscriptions; no new timing API."""

    def __init__(self, agent):
        super().__init__(agent)
        base = self.binding

        def signal(leaf):
            path = self.paths['sc'] + leaf
            value = memory_signal(agent.dut, path)
            if value is None:
                raise RuntimeError(f'Missing static SC-used observation signal: {path}')
            return value
        pipeline = Bundle(thresholds=tuple((signal(f'scThreshold_{way}_value') for way in range(4))), next_values=tuple((signal(f't1_writeThresVec_{way}_value') for way in range(4))), t0_valid_vec=tuple((signal(f't0_writeValidVec_{slot}') for slot in range(8))), t1_registered_vec=tuple((signal(f't1_writeValidVecReg_{slot}') for slot in range(8))), t1_valid_vec=tuple((signal(f't1_writeValidVec_{slot}') for slot in range(8))), t1_fire=signal('t1_fire'), t1_write_valid=signal('t1_writeValid'), t2_write_valid=signal('t2_writeValid'))
        bits = base.bits
        self.binding = PortBinding(base.clock, Bundle(buffers=bits.buffers, t0=bits.t0, training=bits.training, prediction=bits.prediction, used_pipeline=pipeline), 'bpu.sc.used_full_state_and_threshold')
