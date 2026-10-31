"""Native port binding and passive output sampling for OrderedPermitCtrl."""
from dataclasses import dataclass

from toffee import Bundle

from .encoding import encode, output_names
from .types import Beat, Observation


@dataclass(frozen=True, slots=True)
class Ports:
    clock: object
    reset: object
    inputs: Bundle
    outputs: Bundle

    @classmethod
    def bind(cls, dut):
        input_names = []
        for index in range(8):
            input_names.extend((
                f'in_entries_{index}_valid', f'in_entries_{index}_static_uopType',
                f'in_entries_{index}_static_robIdx_flag', f'in_entries_{index}_static_robIdx_value',
                f'in_entries_{index}_static_uopIdx', f'in_entries_{index}_static_lastUop',
                f'in_entries_{index}_dynamic_exception', f'in_entries_{index}_dynamic_state',
            ))
        input_names.extend((
            'in_splitDoneUpdate_valid', 'in_splitDoneUpdate_bits_entryIdxOH',
            'in_redirect_valid', 'in_redirect_bits_level',
            'in_redirect_bits_robIdx_flag', 'in_redirect_bits_robIdx_value',
        ))
        inputs = Bundle(**{name: getattr(dut, name) for name in input_names})
        outputs = Bundle(**{name: getattr(dut, name) for name in output_names()})
        return cls(dut.clock, dut.reset, inputs, outputs)


class Monitor:
    def __init__(self, ports):
        self.ports = ports
        self.sampler = ports.outputs.compile_sampler()

    def sample(self, dut):
        dut.RefreshComb()
        value = self.sampler()
        return Observation(tuple(bool(getattr(value, name).as_int()) for name in output_names()))


def drive(ports, beat: Beat):
    ports.inputs.drive(encode(beat))
