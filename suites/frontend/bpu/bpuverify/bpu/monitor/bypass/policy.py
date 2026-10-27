"""Readonly parent training controls and exact aging counter, kept out of testcases."""
from bpuverify.common.env.memory_direct import memory_signal
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.monitor.bypass import index as _v23

class SramMonitor(_v23.SramMonitor):
    def __init__(self,agent):
        super().__init__(agent)
        prefix=self.prefixes[0].removesuffix("MicroTageTable.wbuffer.")
        def signal(name):
            value=memory_signal(agent.dut, prefix+name)
            if value is None:
                raise RuntimeError(f"MicroTAGE training/aging leaf unavailable: {prefix+name}")
            return value
        boundary=Bundle(low_tick=signal("lowTickCounter"),need_alloc=signal("t1_needAlloc"),
            normal_mask=signal("t1_normalAllocMask"),fire=signal("t1_fire"))
        self.binding=PortBinding(agent.dut.clock,Bundle(**dict(self.binding.bits),policy_boundary=boundary),
            "bpu.integrated_microtage_parent_training_and_aging")
