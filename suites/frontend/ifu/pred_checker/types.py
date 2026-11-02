"""Immutable, byte-addressed observations with explicit sampling-slot identity."""
from dataclasses import dataclass

from suites.frontend.ifu.model.pred_checker import PC_BITS, Redirect, Request


@dataclass(frozen=True)
class Interface:
    instruction_lanes: int = 35
    cross_block_lanes: int = 34
    padding_lane: int = 35
    pc_bits: int = PC_BITS


@dataclass(frozen=True)
class Frame:
    request: Request = Request(valid=0)
    reset: bool = False
    padding_pc: int = 0  # Unselectable target adder: coverage noise, not an instruction.

    def __post_init__(self):
        if not isinstance(self.request, Request):
            raise TypeError('PredChecker requires a semantic Request transaction')
        if not isinstance(self.reset, (bool, int)) or self.reset not in (0, 1):
            raise ValueError('reset must be boolean')
        if (not isinstance(self.padding_pc, int) or not 0 <= self.padding_pc < (1 << PC_BITS)
                or self.padding_pc & 1):
            raise ValueError('padding_pc must be a halfword-aligned guarded byte PC')


@dataclass(frozen=True)
class BeforeEdge:
    fixed_instr_valid: tuple[int, ...]
    redirect: Redirect


@dataclass(frozen=True)
class CheckedCycle:
    sequence: int  # Local input-slot identity, not an invented hardware response tag.
    fixed_instr_valid: tuple[int, ...]
    previous_redirect: Redirect
    redirect: Redirect
    combinational_tick: int
    registered_tick: int
