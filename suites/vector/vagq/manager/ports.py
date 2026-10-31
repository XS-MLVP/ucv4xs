"""Static driver binding plus native committed-public-pin observations."""
from dataclasses import dataclass

from toffee import Bundle

from suites.vector.vagq.native import public_signals
from .encoding import WIDTHS, decode
from .types import Allocation, Boundary


@dataclass(frozen=True, slots=True)
class Ports:
    clock: object
    reset: object
    stimulus: Bundle
    observed: Bundle

    @classmethod
    def bind(cls, dut):
        read = public_signals(dut, 'VAGQManager', WIDTHS)
        inputs = {name.removeprefix('in_'): getattr(dut, name)
                  for name in WIDTHS if name.startswith('in_')}
        return cls(
            dut.clock, dut.reset, Bundle(**inputs),
            Bundle(
                reset=read['reset'],
                control=Bundle(**{name: read['in_' + name] for name in inputs}),
                result=Bundle(valid=read['out_allocValid'],
                              start=read['out_entryIdx'], mask=read['out_allocMask']),
            ),
        )


def snapshot(sample) -> Boundary:
    return Boundary(
        bool(sample.reset.as_int()),
        decode({name: value.as_int() for name, value in sample.control.items()}),
        Allocation(sample.result.valid.as_int(), sample.result.start.as_int(),
                   sample.result.mask.as_int()),
    )
