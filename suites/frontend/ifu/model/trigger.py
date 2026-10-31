"""Reference model for FrontendTrigger.

Intent: the frontend only needs to answer, for each fetch lane, "would any
enabled and configured instruction-address trigger fire here, and which action
must be attached?".  A trigger compares the lane PC against ``tdata2`` using
the supported match modes (equal, greater-or-equal, less-than), and is gated by
its enable bit, the ``select`` bit (this unit supports PC triggers only), and
debug mode.  Chaining follows the Sdtrig rule for the legal chain length of
this machine: a chained trigger does not fire itself; it arms the immediately
following trigger, which may fire only when both hit and their timing bits
agree.  The chain is therefore pairwise (the CSR forbids adjacent chain bits,
i.e. chains longer than two triggers).

Actions are resolved per lane: entering debug mode has priority over raising a
breakpoint, and a breakpoint is only possible when the CSR allows its
exception.  Everything else is "no action".
"""

from __future__ import annotations

from dataclasses import dataclass

TRIGGERS = 4
LANES = 36
PC_MASK = (1 << 50) - 1

EQ = 0
GE = 2
LT = 3

ACTION_BREAKPOINT = 0
ACTION_DEBUG = 1
ACTION_NONE = 15


@dataclass
class Trigger:
    match_type: int = 0
    select: int = 0
    timing: int = 0
    action: int = ACTION_NONE
    chain: int = 0
    tdata2: int = 0


@dataclass
class Update:
    valid: int = 0
    index: int = 0
    trigger: Trigger | None = None


@dataclass
class Inputs:
    update: Update
    enable: tuple[int, int, int, int]
    debug_mode: int
    can_raise_breakpoint: int
    pcs: tuple[int, ...]


def compare(data: int, tdata2: int, match_type: int) -> bool:
    """Architectural Sdtrig comparison.

    ``tdata2`` is a 64-bit RW CSR field.  The fetch PC is a 50-bit address
    (``VAddrBits``), zero-extended to the compare width; it must not be masked
    to lose the guard/sign information, and ``tdata2`` must not be truncated to
    the implemented address width either.  Truncating the trigger value would
    turn "no address can ever equal 2**50" into a match at PC 0, and would make
    ``PC < 2**50`` false for the less-than relation.

    The RTL currently compares only ``VAddrBits`` of tdata2 (see
    ``TriggerCmpConsecutive``); this model deliberately keeps the architectural
    width so the mismatch is visible instead of being copied into the oracle.
    """

    left = data & PC_MASK
    right = tdata2
    if match_type == EQ:
        return left == right
    if match_type == GE:
        return left >= right
    if match_type == LT:
        return left < right
    return False


def can_fire(hit: list[bool], timing: list[int], chain: list[int]) -> list[bool]:
    fired = []
    for index in range(TRIGGERS):
        if index == 0:
            chain_ok = True
            timing_ok = True
        else:
            previous = index - 1
            chain_ok = (bool(chain[previous]) and hit[previous]) or not chain[previous]
            timing_same = timing[previous] == timing[index]
            link_ends = bool(chain[previous]) and not chain[index]
            timing_ok = (link_ends and timing_same) or not chain[previous]
        fired.append(bool(chain_ok and timing_ok and hit[index] and not chain[index]))
    return fired


class TriggerModel:
    def __init__(self) -> None:
        self.triggers = [Trigger() for _ in range(TRIGGERS)]
        self.enable = [0, 0, 0, 0]

    def lane_actions(self, inputs: Inputs, pcs: tuple[int, ...] | None = None) -> list[int]:
        lane_pcs = inputs.pcs if pcs is None else pcs
        hits = []
        for trigger, enabled in zip(self.triggers, self.enable):
            row = []
            for pc in lane_pcs:
                active = bool(enabled and not trigger.select and not inputs.debug_mode)
                row.append(active and compare(pc, trigger.tdata2, trigger.match_type))
            hits.append(row)
        actions = []
        for lane in range(LANES):
            fired = can_fire([hits[index][lane] for index in range(TRIGGERS)],
                             [trigger.timing for trigger in self.triggers],
                             [trigger.chain for trigger in self.triggers])
            selected = [self.triggers[index].action for index, fire in enumerate(fired) if fire]
            if ACTION_DEBUG in selected:
                actions.append(ACTION_DEBUG)
            elif inputs.can_raise_breakpoint and ACTION_BREAKPOINT in selected:
                actions.append(ACTION_BREAKPOINT)
            else:
                actions.append(ACTION_NONE)
        return actions

    def tick(self, inputs: Inputs) -> None:
        if inputs.update.valid:
            self.triggers[inputs.update.index] = inputs.update.trigger or Trigger()
        self.enable = list(inputs.enable)
