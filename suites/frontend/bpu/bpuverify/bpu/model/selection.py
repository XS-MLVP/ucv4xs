"""Semantic selection/repair rules for independently predicted candidates.

These functions take owned reference predictions, not sampled DUT results.
They do not yet constitute a complete composed BPU or a learned table model.
Addresses use the existing integrated halfword units.
"""
from dataclasses import dataclass, replace
from enum import IntEnum


class Kind(IntEnum):
    NONE = 0
    CONDITIONAL = 1
    DIRECT = 2
    INDIRECT = 3


class StackAction(IntEnum):
    NONE = 0
    RETURN = 1
    CALL = 2
    RETURN_AND_CALL = 3


@dataclass(frozen=True, slots=True)
class Branch:
    position: int
    target: int
    kind: Kind
    taken: bool = True
    action: StackAction = StackAction.NONE

    def __post_init__(self):
        if type(self.position) is not int or not 0 <= self.position < 16:
            raise ValueError('BPU branch position must fit four bits')
        if type(self.target) is not int or not 0 <= self.target < 1 << 50:
            raise ValueError('BPU branch target must fit the guarded halfword address')
        if type(self.kind) is not Kind or type(self.action) is not StackAction or type(self.taken) is not bool:
            raise ValueError('BPU selection requires semantic branch kind, action and direction')


@dataclass(frozen=True, slots=True)
class Choice:
    branch: Branch
    owner: int | None
    source: str


def fallthrough(pc):
    if type(pc) is not int or not 0 <= pc < 1 << 50:
        raise ValueError('BPU PC must fit the guarded halfword address')
    aligned = (pc // 8) * 8
    target = aligned + 16
    # A fetch cannot cross the current 4-KiB byte page.
    target = min(target, (pc // 2048 + 1) * 2048)
    return Choice(Branch(target - aligned - 1, target % (1 << 50), Kind.NONE, False), None, 'fallthrough')


def first_taken(entries, corrections, fallback, *, source):
    if len(entries) != len(corrections):
        raise ValueError('one optional direction is required per reference candidate')
    candidates = []
    for owner, (entry, correction) in enumerate(zip(entries, corrections, strict=True)):
        if correction is not None and type(correction) is not bool:
            raise ValueError('a reference correction is bool or absent, not a valid/one-hot vector')
        if entry is None:
            continue
        taken = entry.kind in (Kind.DIRECT, Kind.INDIRECT) or (entry.kind == Kind.CONDITIONAL
            and (entry.taken if correction is None else correction))
        if taken:
            candidates.append((entry.position, owner, replace(entry, taken=True)))
    if not candidates:
        return fallback
    # CompareMatrix keeps strict order above the diagonal and its complement
    # below it. Equal positions therefore prefer the larger candidate index.
    # This tie policy is separate from duplicate cleanup's lower-way survivor.
    _, owner, branch = min(candidates, key=lambda value: (value[0], -value[1]))
    return Choice(branch, owner, source)


def early(pc, *, micro=None, ahead=(), short_history=(), return_address=None):
    fallback = fallthrough(pc)
    if any(entry is not None for entry in ahead):
        result = first_taken(ahead, short_history, fallback, source='ahead')
    else:
        result = fallback if micro is None or not micro.taken else Choice(micro, None, 'micro')
    if result.branch.taken and result.branch.action == StackAction.RETURN and return_address is not None:
        result = replace(result, branch=replace(result.branch, target=return_address), source='micro-return-stack')
    return result


def middle(pc, entries, raw_providers):
    return first_taken(entries, raw_providers, fallthrough(pc), source='main')


def final(pc, entries, tagged, statistical, *, indirect_target=None, return_address=None):
    if len(tagged) != len(statistical):
        raise ValueError('final reference corrections must have equal candidate counts')
    corrections = tuple(sc if sc is not None else tag for tag, sc in zip(tagged, statistical, strict=True))
    result = first_taken(entries, corrections, fallthrough(pc), source='main')
    branch = result.branch
    if branch.taken and branch.action == StackAction.RETURN and return_address is not None:
        result = replace(result, branch=replace(branch, target=return_address), source='return-stack')
    elif branch.taken and branch.kind == Kind.INDIRECT and not branch.action & StackAction.RETURN and indirect_target is not None:
        result = replace(result, branch=replace(branch, target=indirect_target), source='indirect-history')
    return result


def middle_repair(early_choice, middle_choice):
    first, later = early_choice.branch, middle_choice.branch
    return first.taken != later.taken or (later.taken and
        (first.position, first.kind, first.action) != (later.position, later.kind, later.action))


def final_repair(early_choice, middle_choice, final_choice, *, corrected_middle):
    before, after = middle_choice.branch, final_choice.branch
    if before.taken != after.taken or middle_choice.owner != final_choice.owner:
        return True
    if not after.taken:
        return False
    baseline = before if corrected_middle else early_choice.branch
    if final_choice.source in ('return-stack', 'indirect-history'):
        return after.target != baseline.target
    # A compressed early target is not architectural truth. Comparing only
    # its low bits would reproduce the known INT-013/018 RTL blind spot.
    # An S2 repair already consumed Main's full target; otherwise S3 must
    # correct every differing bit, including a high-region-only mismatch.
    return not corrected_middle and after.target != baseline.target
