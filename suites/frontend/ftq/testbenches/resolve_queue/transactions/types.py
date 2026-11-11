"""ResolveQueue typed transactions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResolveReport:
    """One resolution; pc/target are 49-bit halfword Pc.addr coordinates.

    Backend/IFU redirects use full byte addresses instead. This existing leaf
    API preserves its raw Pc coordinates; it does not silently drop a 50th bit
    or claim that an unshifted byte address was converted by the driver.
    """

    index: int
    pc: int
    offset: int
    target: int
    taken: int = 1
    mispredict: int = 1
    branch_type: int = 1
    ras_action: int = 0
    flag: int = 0

    def __post_init__(self) -> None:
        limits = dict(index=64, flag=2, pc=1 << 49, target=1 << 49,
                      offset=32, taken=2, mispredict=2, branch_type=4, ras_action=4)
        for name, limit in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value < limit:
                raise ValueError(f'{name} must be an integer in 0..{limit-1}')


@dataclass(frozen=True, slots=True)
class Branch:
    position: int
    target: int
    taken: int
    mispredict: int
    branch_type: int
    ras_action: int


@dataclass(frozen=True, slots=True)
class Training:
    """One owned ResolveEntry offered to the BPU training port."""

    index: int
    flag: int
    start_pc: int
    branches: tuple[Branch, ...]
    valid_mask: int = -1

    def __post_init__(self):
        # Models with a compact semantic branch tuple expect the admitted
        # prefix. The native decoder always supplies the real per-slot mask.
        if self.valid_mask == -1:
            object.__setattr__(self, 'valid_mask', (1 << len(self.branches)) - 1)


@dataclass(frozen=True, slots=True)
class Ownership:
    """Internal circular-pointer state, used only for identity evidence."""

    enq: int
    deq: int
