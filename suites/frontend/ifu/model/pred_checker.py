"""Reference model for PredChecker.

Intent: the branch predictor says whether a fetched instruction is taken.  The
instruction's own predecode class says whether it is *allowed* to be taken:

* a direct jump, an indirect jump and a return must be predicted taken;
* a conditional branch may be either;
* a non-control-flow instruction must not be predicted taken;
* a predictor that points at an invalid lane is a fault by itself.

The checker must stop the speculative fetch window at the first violation
(keeping instructions before and including that lane), and tell the FTQ how to
redirect: the computed target for a direct jump or conditional branch, or the
sequential next PC when this stage cannot know the target (indirect, return,
non-CFI, invalid lane).  Attribute and class flags travel with the redirect so
the FTQ can train or blame the right predictor.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

SLOTS = 36
PC_BITS = 51  # GuardedVAddrBits: byte PC plus one overflow/guard bit
PC_MASK = (1 << PC_BITS) - 1

NONE = 0
CONDITIONAL = 1
DIRECT = 2
INDIRECT = 3

POP = 1
PUSH = 2


@dataclass
class Instr:
    valid: int = 0
    is_rvc: int = 0
    is_pred_taken: int = 0
    invalid_taken: int = 0
    block_sel: int = 0
    end_offset: int = 0
    is_cross_block: int = 0
    branch_type: int = NONE
    ras_action: int = 0
    pc: int = 0
    jump_offset: int = 0

    @property
    def has_pop(self) -> bool:
        return bool(self.ras_action & POP)

    @property
    def is_direct(self) -> bool:
        return self.branch_type == DIRECT

    @property
    def is_indirect(self) -> bool:
        return self.branch_type == INDIRECT

    @property
    def is_cond(self) -> bool:
        return self.branch_type == CONDITIONAL

    @property
    def not_cfi(self) -> bool:
        return self.branch_type == NONE


@dataclass
class Request:
    valid: int = 1
    instrs: list[Instr] = field(default_factory=lambda: [Instr() for _ in range(SLOTS)])


@dataclass
class Redirect:
    valid: int = 0
    target: int = 0
    taken: int = 0
    invalid_taken: int = 0
    not_cfi_taken: int = 0
    is_rvc: int = 0
    block_sel: int = 0
    branch_type: int = NONE
    ras_action: int = 0
    end_offset: int = 0
    is_cross_block: int = 0


@dataclass
class Prediction:
    fixed_instr_valid: tuple[int, ...]
    redirect: Redirect
    fault_index: int
    fault_class: str | None


def fault_classes(request: Request) -> list[str | None]:
    classes: list[str | None] = []
    for instruction in request.instrs:
        if instruction.invalid_taken:
            classes.append("invalidTaken")
            continue
        if instruction.valid and instruction.not_cfi and instruction.is_pred_taken:
            classes.append("notCfiTaken")
            continue
        if instruction.valid and instruction.is_direct and not instruction.is_pred_taken:
            classes.append("jalFault")
            continue
        if instruction.valid and instruction.is_indirect and not instruction.has_pop \
                and not instruction.is_pred_taken:
            classes.append("jalrFault")
            continue
        if instruction.valid and instruction.has_pop and not instruction.is_pred_taken:
            classes.append("retFault")
            continue
        classes.append(None)
    return classes


def predict(request: Request) -> Prediction:
    classes = fault_classes(request)
    fault_index = next((index for index, name in enumerate(classes) if name is not None), None)
    fixed = []
    for index, instruction in enumerate(request.instrs):
        keep = fault_index is None or index <= fault_index
        fixed.append(int(instruction.valid and keep))
    redirect = Redirect()
    if fault_index is not None:
        lane = request.instrs[fault_index]
        cls = classes[fault_index]
        assert cls is not None
        is_jump = bool(lane.valid and (lane.is_direct or lane.is_cond))
        target = lane.pc + (lane.jump_offset if is_jump else
                            (2 if (lane.is_rvc or lane.invalid_taken) else 4))
        # ``taken`` is the prediction's taken-ness, not an instruction-valid
        # qualifier: for an invalid-taken lane the class comes from the
        # speculative predecode and may still say "taken".
        taken = bool((lane.is_indirect or lane.is_direct or
                      (lane.is_pred_taken and not lane.not_cfi)) and request.valid)
        redirect = Redirect(
            valid=int(request.valid),
            target=target & PC_MASK,
            taken=int(taken),
            invalid_taken=lane.invalid_taken,
            # These are raw lane facts, not derived from which fault class won
            # the priority encoder: a lane can be both invalid-taken and a
            # non-CFI take at the same time.
            not_cfi_taken=int(bool(lane.valid and lane.not_cfi and lane.is_pred_taken)),
            is_rvc=lane.is_rvc,
            block_sel=lane.block_sel,
            branch_type=NONE if lane.invalid_taken else lane.branch_type,
            ras_action=0 if lane.invalid_taken else lane.ras_action,
            end_offset=lane.end_offset & 0x1F,
            is_cross_block=lane.is_cross_block,
        )
    return Prediction(tuple(fixed), redirect,
                      -1 if fault_index is None else fault_index,
                      None if fault_index is None else classes[fault_index])
