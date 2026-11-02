"""Fixed-configuration reason/control binding, never exposed to feature tests."""
from dataclasses import dataclass

from toffee import Bundle

from suites.frontend.ifu.model.perf import FTQ_BITS, Inputs, WIDTH


@dataclass(frozen=True)
class Frame:
    inputs: Inputs = Inputs()
    reset: bool = False

    def __post_init__(self):
        if not isinstance(self.inputs, Inputs):
            raise TypeError('PerfAnalysis requires a semantic Inputs transaction')
        if not isinstance(self.reset, int) or self.reset not in (0, 1):
            raise ValueError('PerfAnalysis reset must be a boolean encoding')


CONTROL_PORTS = {
    'ifu_wb_redirect': 'io_ifuPerfCtrl_ifuWbRedirect',
    'backend_redirect': 'io_topdownIn_backendRedirectTopdown_backendRedirect',
    'control_flow_redirect': 'io_topdownIn_backendRedirectTopdown_controlFlowRedirect',
    'memory_violation_redirect': 'io_topdownIn_backendRedirectTopdown_memoryViolationRedirect',
    'tage_miss': 'io_topdownIn_backendRedirectTopdown_tageMissBubble',
    'ittage_miss': 'io_topdownIn_backendRedirectTopdown_ittageMissBubble',
    'ras_miss': 'io_topdownIn_backendRedirectTopdown_rasMissBubble',
    'icache_miss': 'io_topdownIn_icacheTopdown_iCacheMissBubble',
    'itlb_miss': 'io_topdownIn_icacheTopdown_itlbMissBubble',
}


class PerfPorts:
    def __init__(self, dut):
        def bind(name, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != 1:
                raise ValueError(f'{name}: expected native width1, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        names = ['reset', *CONTROL_PORTS.values(),
                 *(f'io_topdownIn_ftqTopdown_reasons_{bit}' for bit in FTQ_BITS)]
        self.inputs = {name: bind(name) for name in names}
        self.bits = Bundle(**self.inputs)
        self.outputs = tuple(bind(f'io_topdownOut_topdown_reasons_{bit}', output=True)
                              for bit in range(WIDTH))
        bind('clock')
        actual = {name for name, signal in vars(dut).items() if name not in {'dut', 'clock'}
                  and callable(getattr(signal, 'IsInIO', None)) and signal.IsInIO() and not signal.IsOutIO()}
        if actual != set(names):
            raise ValueError(f'PerfAnalysis input ownership mismatch: {actual ^ set(names)}')

    def encode(self, frame):
        if not isinstance(frame, Frame):
            raise TypeError('PerfAnalysis requires a semantic Frame')
        values = {port: getattr(frame.inputs, field) for field, port in CONTROL_PORTS.items()}
        values.update((f'io_topdownIn_ftqTopdown_reasons_{bit}', (frame.inputs.ftq_bits >> bit) & 1)
                      for bit in FTQ_BITS)
        values['reset'] = int(frame.reset)
        for name, value in values.items():
            width = max(1, int(self.inputs[name].mWidth))
            if not 0 <= value < (1 << width):
                raise ValueError(f'{name} does not fit native width {width}')
        return values

    def capture(self, event):
        return sum(int(signal.value) << bit for bit, signal in enumerate(self.outputs))
