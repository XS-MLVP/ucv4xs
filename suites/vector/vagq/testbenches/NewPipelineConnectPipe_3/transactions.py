"""NewPipelineConnectPipe_3 payload transactions and one-slot protocol beats."""
from dataclasses import dataclass


def _check(name, value, width):
    if not isinstance(value, int) or not 0 <= value < 1 << width:
        raise ValueError(f'{name} does not fit unsigned {width} bits: {value!r}')


@dataclass(frozen=True, slots=True)
class Pipe3Payload:
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    is_load: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    issue_mask: int = 0

    def __post_init__(self):
        for name, value, width in (
            ('entry_idx', self.entry_idx, 3), ('rob_flag', self.rob_flag, 1),
            ('rob_value', self.rob_value, 9), ('is_load', self.is_load, 1),
            ('lq_value', self.lq_value, 7), ('sq_first_flag', self.sq_first_flag, 1),
            ('sq_second_flag', self.sq_second_flag, 1), ('sq_value', self.sq_value, 6),
            ('issue_mask', self.issue_mask, 16),
        ):
            _check(name, value, width)


@dataclass(frozen=True, slots=True)
class Beat:
    in_valid: bool = False
    out_ready: bool = False
    right_out_fire: bool = False
    is_flush: bool = False
    payload: Pipe3Payload = Pipe3Payload()


@dataclass(frozen=True, slots=True)
class Observation:
    in_ready: bool
    out_valid: bool
    payload: Pipe3Payload
