"""Required native binding, whole-command encoding and stable-phase capture."""
from toffee import Bundle

from .transactions import DelayOutput, PAYLOAD_FIELDS, REDIRECT_FIELDS


class DelayPorts:
    def __init__(self, dut):
        self.dut = dut
        self.input_names = ('reset', 'io_in_valid',
            *('io_in_bits_' + field for field in PAYLOAD_FIELDS),
            'io_redirect_valid', 'io_redirect_bits_level', 'io_redirect_bits_robIdx_flag',
            'io_redirect_bits_robIdx_value', 'io_redirect_bits_robIdx_isFormer')
        self.inputs = {name: getattr(dut, name) for name in self.input_names}
        self.bits = Bundle(**self.inputs)
        self.valid = dut.io_out_valid
        self.outputs = tuple(getattr(dut, 'io_out_bits_' + field) for field in PAYLOAD_FIELDS)

    def encode(self, command):
        values = {'reset': int(command.reset), 'io_in_valid': command.valid}
        values.update(('io_in_bits_' + field, value)
                      for field, value in zip(PAYLOAD_FIELDS, command.bits, strict=True))
        redirect = dict(zip(REDIRECT_FIELDS, command.redirect, strict=True))
        values.update(io_redirect_valid=redirect['valid'], io_redirect_bits_level=redirect['level'],
                      io_redirect_bits_robIdx_flag=redirect['flag'],
                      io_redirect_bits_robIdx_value=redirect['value'],
                      io_redirect_bits_robIdx_isFormer=redirect['former'])
        for name, value in values.items():
            width = max(1, int(self.inputs[name].mWidth))
            if not 0 <= value < (1 << width):
                raise ValueError(f'{name} does not fit actual DUT width {width}')
        return values

    def capture(self, event):
        return DelayOutput(int(self.valid.value), tuple(int(signal.value) for signal in self.outputs))
