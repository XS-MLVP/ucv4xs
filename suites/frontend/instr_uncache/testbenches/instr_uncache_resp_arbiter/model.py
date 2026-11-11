"""1:1 response-arbiter contract for Arbiter1_InstrUncacheResp.

``nMmioEntry == 1`` makes Chisel's Arbiter degenerate to a wiring element: one
input request is granted unconditionally and all response fields are passed
through.  The contract still has two obligations that are tested explicitly:
``valid`` qualifies every payload field, and the three error/retry flags are
independent bits (an error in one must not rewrite another).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Inputs:
    in_valid: int = 0
    in_data: int = 0
    in_corrupt: int = 0
    in_denied: int = 0
    in_need_resend: int = 0

    def __post_init__(self) -> None:
        for name in ("in_valid", "in_corrupt", "in_denied", "in_need_resend"):
            if getattr(self, name) not in (0, 1):
                raise ValueError(f"{name} must be 0 or 1")
        if not 0 <= self.in_data < (1 << 32):
            raise ValueError("in_data must be an unsigned 32-bit value")


@dataclass(frozen=True)
class Outputs:
    out_valid: int
    out_data: int
    out_corrupt: int
    out_denied: int
    out_need_resend: int

    def as_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def arbiter_outputs(inputs: Inputs) -> Outputs:
    """The only legal mapping for a one-input grant: identity on every field."""
    if not isinstance(inputs, Inputs):
        raise TypeError("arbiter model requires protocol Inputs")
    return Outputs(inputs.in_valid, inputs.in_data, inputs.in_corrupt,
                   inputs.in_denied, inputs.in_need_resend)


def reset_snapshot() -> Outputs:
    return Outputs(0, 0, 0, 0, 0)


ArbiterInputs = Inputs
ArbiterOutputs = Outputs
