"""Strict transaction types for the generated SRAM broadcast controls.

These controls are shared by the DataBank and MetaBank adapters, but they are
not silently folded into either DUT's functional payload.  The type preserves
the distinction between a declared persistent control level and a functional
read/write/MBIST offer.
"""

from __future__ import annotations

from dataclasses import dataclass


def _bit(value: int, name: str) -> None:
    if type(value) is not int or value not in (0, 1):
        raise ValueError(f"ICache SRAM control {name} requires an exact 0/1 integer")


@dataclass(frozen=True, slots=True)
class SramControl:
    hold: int = 0
    bypass: int = 0
    bp_clken: int = 0
    aux_clk: int = 0
    aux_ckbp: int = 0
    mcp_hold: int = 0
    cgen: int = 0

    def __post_init__(self) -> None:
        for name in ("hold", "bypass", "bp_clken", "aux_clk", "aux_ckbp", "mcp_hold", "cgen"):
            _bit(getattr(self, name), name)

    def as_tuple(self) -> tuple[int, ...]:
        return (self.hold, self.bypass, self.bp_clken, self.aux_clk,
                self.aux_ckbp, self.mcp_hold, self.cgen)


@dataclass(frozen=True, slots=True)
class SramControls:
    ways: tuple[SramControl, ...]

    def __post_init__(self) -> None:
        if type(self.ways) not in (tuple, list) or not self.ways:
            raise ValueError("ICache SRAM controls require at least one physical group")
        if any(type(value) is not SramControl for value in self.ways):
            raise ValueError("ICache SRAM controls require typed per-group entries")
        object.__setattr__(self, "ways", tuple(self.ways))

    @classmethod
    def idle(cls, groups: int) -> "SramControls":
        if type(groups) is not int or groups <= 0:
            raise ValueError("ICache SRAM controls require a positive physical group count")
        return cls((SramControl(),) * groups)

    def as_tuples(self) -> tuple[tuple[int, ...], ...]:
        return tuple(value.as_tuple() for value in self.ways)

    def require_groups(self, groups: int) -> None:
        if len(self.ways) != groups:
            raise ValueError(f"ICache SRAM controls require exactly {groups} physical groups")


def encode_controls(controls: SramControls) -> dict[str, tuple[dict[str, int], ...]]:
    if type(controls) is not SramControls:
        raise ValueError("ICache SRAM control encoding requires SramControls")
    return {
        "ways": tuple({
            "hold": value.hold,
            "bypass": value.bypass,
            "bp_clken": value.bp_clken,
            "aux_clk": value.aux_clk,
            "aux_ckbp": value.aux_ckbp,
            "mcp_hold": value.mcp_hold,
            "cgen": value.cgen,
        } for value in controls.ways)
    }
