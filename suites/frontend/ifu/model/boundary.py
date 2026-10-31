"""Reference model for InstrBoundary.

Intent: a fetch window is a byte stream of 16-bit slots.  The compressed-map
bit at the start of an instruction says the instruction occupies one slot;
otherwise it occupies two.  A carry-in means slot 0 is the second half of an
instruction that started in the previous window.  From that stream the module
must answer, for every slot:

* does an instruction start here (and is it therefore a valid instruction),
* how wide is it and which half of a fetch block owns it,
* where does its byte range sit inside that block,
* does it end here (the mask used to count instructions in a prefix), and
* does the window end immediately after the first half of a full-width
  instruction, so the next fetch must resume the second half.

A full-width instruction that begins in the last slot of a fall-through first
block and continues into the second block is special: it is one instruction
whose two halves come from different blocks.  The model marks it, rather than
splitting it into two instructions.
"""

from __future__ import annotations

from dataclasses import dataclass

SLOTS = 32


@dataclass(frozen=True)
class BoundaryInput:
    block0_size: int
    taken_valid: int
    taken_offset: int
    block1_valid: int
    maybe_rvc: int
    block_sel: int
    first_instr_is_half_rvi: int
    total_end_pos: int
    index: tuple[int, ...] | None = None


@dataclass(frozen=True)
class BoundaryOutput:
    valid: tuple[int, ...]
    is_rvc: tuple[int, ...]
    is_cross_block: tuple[int, ...]
    instr_end_mask: tuple[int, ...]
    start_offset: tuple[int, ...]
    end_offset: tuple[int, ...]
    block_sel: tuple[int, ...]
    index: tuple[int, ...]
    first_end_is_half_rvi: int
    total_end_is_half_rvi: int


def starts(window: BoundaryInput) -> list[bool]:
    start = [False] * SLOTS
    start[0] = not bool(window.first_instr_is_half_rvi)
    for slot in range(1, SLOTS):
        previous = slot - 1
        # A previous slot that is not a start is the second half of an RVI;
        # a start is one slot wide exactly when the map marks it compressed.
        start[slot] = (not start[previous]) or bool((window.maybe_rvc >> previous) & 1)
    return start


def predict(window: BoundaryInput) -> BoundaryOutput:
    if not 1 <= window.block0_size <= SLOTS:
        raise ValueError(f"block0_size outside 1..{SLOTS}: {window.block0_size}")
    for name in ("taken_offset", "total_end_pos"):
        value = getattr(window, name)
        if not 0 <= value < SLOTS:
            raise ValueError(f"{name} outside the 32-slot window: {value}")
    start = starts(window)
    is_rvc = [start[slot] and bool((window.maybe_rvc >> slot) & 1) for slot in range(SLOTS)]
    sel = [(window.block_sel >> slot) & 1 for slot in range(SLOTS)]
    start_offset = [slot - (window.block0_size if sel[slot] else 0) for slot in range(SLOTS)]
    # endOffset is a five-bit block-relative field; the end slot after the
    # last slot of a block cannot be represented and wraps to zero, which is
    # also the marker used for a cross-block instruction.
    end_offset = [(start_offset[slot] + (0 if is_rvc[slot] else 1)) & 0x1F
                  for slot in range(SLOTS)]
    valid = [bool(window.first_instr_is_half_rvi) or start[0]] + start[1:]
    # The block-crossing case can only be the last slot; the RTL deliberately
    # excludes slot 31 from the general expression.
    cross = [False] * SLOTS
    for slot in range(SLOTS - 1):
        cross[slot] = bool(
            window.block1_valid and not window.taken_valid
            and slot == window.taken_offset and not sel[slot] and sel[slot + 1]
            and not is_rvc[slot]
        )
    end_mask = [(not start[slot]) or is_rvc[slot] for slot in range(SLOTS)]
    index = window.index if window.index is not None else tuple(range(SLOTS))
    if len(index) != SLOTS:
        raise ValueError("index must contain 32 entries")
    first_end = start[window.taken_offset] and not bool((window.maybe_rvc >> window.taken_offset) & 1)
    total_end = start[window.total_end_pos] and not bool((window.maybe_rvc >> window.total_end_pos) & 1)
    return BoundaryOutput(
        valid=tuple(int(value) for value in valid),
        is_rvc=tuple(int(value) for value in is_rvc),
        is_cross_block=tuple(int(value) for value in cross),
        instr_end_mask=tuple(int(value) for value in end_mask),
        start_offset=tuple(start_offset),
        end_offset=tuple(end_offset),
        block_sel=tuple(sel),
        index=tuple(index),
        first_end_is_half_rvi=int(first_end),
        total_end_is_half_rvi=int(total_end),
    )


def ends_in_prefix(window: BoundaryInput, last_slot: int) -> int:
    """Architectural count of instructions that end within slots 0..last_slot."""

    predicted = predict(window)
    return sum(predicted.instr_end_mask[: last_slot + 1])
