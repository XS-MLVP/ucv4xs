"""Distinct payload transactions and common one-slot protocol beats."""
from dataclasses import dataclass


def _check(name, value, width):
    if not isinstance(value, int) or not 0 <= value < 1 << width:
        raise ValueError(f'{name} does not fit unsigned {width} bits: {value!r}')


@dataclass(frozen=True, slots=True)
class PipePayload:
    entry_idx: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    is_load: int = 0
    lq_flag: int = 0
    lq_value: int = 0
    sq_first_flag: int = 0
    sq_second_flag: int = 0
    sq_value: int = 0
    elem_idx: int = 0
    data_size: int = 0
    data_mask: int = 0
    pc: int = 0
    ftq_flag: int = 0
    ftq_value: int = 0
    ftq_offset: int = 0
    byte_offset: int = 0
    vaddr: int = 0
    pdest: int = 0

    def __post_init__(self):
        for name, value, width in (
            ('entry_idx', self.entry_idx, 3), ('rob_flag', self.rob_flag, 1),
            ('rob_value', self.rob_value, 9), ('is_load', self.is_load, 1),
            ('lq_flag', self.lq_flag, 1), ('lq_value', self.lq_value, 7),
            ('sq_first_flag', self.sq_first_flag, 1), ('sq_second_flag', self.sq_second_flag, 1),
            ('sq_value', self.sq_value, 6), ('elem_idx', self.elem_idx, 7),
            ('data_size', self.data_size, 3), ('data_mask', self.data_mask, 16),
            ('pc', self.pc, 50), ('ftq_flag', self.ftq_flag, 1), ('ftq_value', self.ftq_value, 6),
            ('ftq_offset', self.ftq_offset, 5), ('byte_offset', self.byte_offset, 4),
            ('vaddr', self.vaddr, 64), ('pdest', self.pdest, 7),
        ):
            _check(name, value, width)


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
    payload: PipePayload | Pipe3Payload = PipePayload()


@dataclass(frozen=True, slots=True)
class Observation:
    in_ready: bool
    out_valid: bool
    payload: PipePayload | Pipe3Payload
