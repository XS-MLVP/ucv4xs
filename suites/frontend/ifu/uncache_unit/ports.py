"""Complete15-input/9-output binding, plus proven pruned response-ready=1."""
from toffee import Bundle

from suites.frontend.ifu.model.uncache import Outputs

from .types import Frame


INPUTS = {
    'flush': ('io_flush', 1), 'req_valid': ('io_req_valid', 1),
    'req_paddr': ('io_req_bits_paddr_addr', 47), 'req_is_mmio': ('io_req_bits_isMmio', 1),
    'req_pbmt': ('io_req_bits_pbmt', 2), 'is_first_instr': ('io_isFirstInstr', 1),
    'ifu_stall': ('io_ifuStall', 1), 'empty_after': ('io_emptyAfter', 1),
    'to_ready': ('io_toUncache_req_ready', 1), 'from_valid': ('io_fromUncache_resp_valid', 1),
    'from_data': ('io_fromUncache_resp_bits_data', 32),
    'from_corrupt': ('io_fromUncache_resp_bits_corrupt', 1),
    'from_denied': ('io_fromUncache_resp_bits_denied', 1),
    'from_need_resend': ('io_fromUncache_resp_bits_needResend', 1),
}
OUTPUTS = {
    'req_ready': ('io_req_ready', 1), 'resp_valid': ('io_resp_valid', 1),
    'resp_data': ('io_resp_bits_uncacheData', 32), 'resp_exception': ('io_resp_bits_exception_value', 3),
    'resp_need_resend': ('io_resp_bits_needResend', 1), 'to_valid': ('io_toUncache_req_valid', 1),
    'to_paddr': ('io_toUncache_req_bits_addr_addr', 47),
    'to_mem_back_mm': ('io_toUncache_req_bits_memBackTypeMM', 1),
    'to_mem_page_nc': ('io_toUncache_req_bits_memPageTypeNC', 1),
}


class UncachePorts:
    response_always_ready = True

    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width {width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        self.bits = Bundle(**{field: bind(name, width) for field, (name, width) in INPUTS.items()},
                           reset=bind('reset', 1))
        self._outputs = Bundle(**{field: bind(name, width, output=True)
                                  for field, (name, width) in OUTPUTS.items()})
        bind('clock', 1)
        if hasattr(dut, 'io_fromUncache_resp_ready'):
            raise ValueError('proven pruned response-ready=1 now exists; migrate explicitly')
        actual = {name for name, signal in vars(dut).items() if name not in {'dut', 'clock'}
                  and callable(getattr(signal, 'IsInIO', None)) and signal.IsInIO() and not signal.IsOutIO()}
        expected = {name for name, _ in INPUTS.values()} | {'reset'}
        if actual != expected:
            raise ValueError(f'Uncache input ownership mismatch: {actual ^ expected}')

    @staticmethod
    def encode(frame):
        if not isinstance(frame, Frame):
            raise TypeError('Uncache requires a semantic Frame')
        values = {field: getattr(frame.inputs, field) for field in INPUTS}
        values['req_paddr'] >>= 1
        return values | {'reset': frame.reset}

    def capture(self, event):
        values = {field: int(value) for field, value in self._outputs.sample().items()}
        values['to_paddr'] <<= 1
        return Outputs(**values)
