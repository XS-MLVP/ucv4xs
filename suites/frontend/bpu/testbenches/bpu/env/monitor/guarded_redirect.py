"""Read-only recovery boundary projection, separate from payload expectations."""
from toffee import Bundle
from toffee.data import signal_width

from suites.frontend.bpu.testbenches.bpu.env.bundle.values import _plain
from suites.frontend.bpu.testbenches.shared.env.monitor.cycle import CycleMonitor
from suites.frontend.bpu.testbenches.shared.env.bundle.bindings import PortBinding
from suites.frontend.bpu.testbenches.shared.env.memory_direct import memory_signal, memory_signal_names


class GuardedRedirectMonitor(CycleMonitor):
    def __init__(self, agent):
        anchors = [n for n in memory_signal_names(agent.dut)
                   if n.endswith('.commonHR.commonHR_ghr')]
        if len(anchors) != 1:
            raise RuntimeError('guarded redirect requires one real CommonHR boundary')
        prefix = anchors[0].removeprefix('TOP.').removesuffix('commonHR.commonHR_ghr')
        def signal(name, width):
            value = memory_signal(agent.dut, prefix + name)
            if value is None or signal_width(value) != width:
                raise RuntimeError(f'guarded redirect boundary missing or wrong width: {name}')
            return value
        bits = Bundle(valid=agent.ports.redirect.valid,
            cfi=agent.ports.redirect.bits.cfi_pc,
            common=signal('commonHR.io_redirect_cfiPc_addr', 49),
            phr=signal('phr.io_train_redirect_bits_cfiPc_addr', 50))
        super().__init__(PortBinding(agent.dut.clock, bits, 'bpu.guarded_redirect'), decoder=_plain)
