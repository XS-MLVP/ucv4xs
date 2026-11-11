"""Exact 2-input/2-output RVC binding; missing or altered pins require migration."""
from toffee import Bundle

from suites.frontend.ifu.testbenches.rvc_expander.transactions import DecodeRequest
from suites.frontend.ifu.testbenches.rvc_expander.transactions import Decoded


class RvcPorts:
    def __init__(self, dut):
        def bind(name, width, *, output=False):
            signal = getattr(dut, name)
            if max(1, int(signal.mWidth)) != width:
                raise ValueError(f'{name}: expected native width {width}, got {signal.mWidth}')
            if ((output and not signal.IsOutIO())
                    or (not output and (not signal.IsInIO() or signal.IsOutIO()))):
                raise ValueError(f'{name}: wrong native port direction')
            return signal

        self.bits = Bundle(word=bind('io_in', 32), fs_is_off=bind('io_fsIsOff', 1))
        self._outputs = Bundle(bits=bind('io_out_bits', 32, output=True),
                               ill=bind('io_ill', 1, output=True))
        actual_inputs = {
            name for name, signal in vars(dut).items()
            if name != 'dut' and callable(getattr(signal, 'IsInIO', None))
            and signal.IsInIO() and not signal.IsOutIO()
        }
        if actual_inputs != {'io_in', 'io_fsIsOff'}:
            raise ValueError(f'RvcExpander input ownership mismatch: {actual_inputs}')
        if hasattr(dut, 'clock') or hasattr(dut, 'reset'):
            raise ValueError('RvcExpander combinational contract has no clock/reset ports')

    @staticmethod
    def encode(request):
        if not isinstance(request, DecodeRequest):
            raise TypeError('RvcExpander requires a semantic DecodeRequest')
        return {'word': request.word, 'fs_is_off': int(request.fs_is_off)}

    def capture(self, event):
        snapshot = self._outputs.sample()
        return Decoded(int(snapshot['bits']), bool(int(snapshot['ill'])))
