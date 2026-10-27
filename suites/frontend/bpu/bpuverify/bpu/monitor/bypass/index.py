"""Static readonly Bundle adds actual index-register control and module metadata output."""
from bpuverify.common.env.memory_direct import memory_signal
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.bpu.monitor.bypass import hash as _v15

class SramMonitor(_v15.SramMonitor):
    def __init__(self,agent):
        super().__init__(agent)
        prefix=self.prefixes[0].removesuffix("MicroTageTable.wbuffer.")
        def signal(name):
            value=memory_signal(agent.dut, prefix+name)
            if value is None:
                raise RuntimeError(f"MicroTAGE index boundary unavailable: {prefix+name}")
            return value
        boundary=Bundle(enable=signal("io_enable"),fire0=signal("io_stageCtrl_s0_fire"),
            fire2=signal("io_stageCtrl_s2_fire"),
            meta_indices=tuple(signal(f"io_meta_bits_readIndex_{table}") for table in range(2)))
        self.binding=PortBinding(agent.dut.clock,Bundle(**dict(self.binding.bits),index_boundary=boundary),
            "bpu.integrated_microtage_SRAM_hash_index_pipeline")
