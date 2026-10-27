"""Clocked native binding for one generated pipe; no protocol model in the probe."""
from dataclasses import dataclass

from toffee import Bundle

from .encoding import encode, output_names
from .specs import Spec
from .types import Beat, Observation


@dataclass(frozen=True, slots=True)
class Ports:
    clock: object
    reset: object
    inputs: Bundle
    outputs: Bundle


def bind(dut, spec: Spec):
    input_names = ('io_in_valid', 'io_out_ready', 'io_rightOutFire', 'io_isFlush') + tuple(
        'io_in_bits_' + wire for _, wire in spec.fields
    )
    ports = Ports(
        dut.clock, dut.reset,
        Bundle(**{name: getattr(dut, name) for name in input_names}),
        Bundle(**{name: getattr(dut, name) for name in output_names(spec)}),
    )
    sampler = ports.outputs.compile_sampler()

    def sample():
        dut.RefreshComb()
        value = sampler()
        payload = spec.payload_type(**{
            attribute: getattr(value, 'io_out_bits_' + wire).as_int()
            for attribute, wire in spec.fields
        })
        return Observation(
            bool(value.io_in_ready.as_int()), bool(value.io_out_valid.as_int()), payload
        )

    return ports, sample
