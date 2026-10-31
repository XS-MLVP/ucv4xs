"""Speculative loop iterations belong to prediction versions, not history wires.

A taken backward conditional extends its original iteration. Every other
outcome ends that loop context. Corrections discard younger speculative
iterations and recompute from the correcting prediction's immutable source.
No CommonHR registers, pointers, observed metadata or table indices are inputs.
"""
from collections import Counter
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.common_history import TARGET_WIDTH
from suites.frontend.bpu.bpu.model.pipeline import Cycle, Token
from suites.frontend.bpu.bpu.model.selection import Branch, Kind

ITERATION_WIDTH = 8
MAX_ITERATIONS = (1 << ITERATION_WIDTH) - 1
PC = 0x40000800
FORWARD, BACKWARD = PC + 0x200, PC - 0x200
POSITION = 1


@dataclass(frozen=True, slots=True)
class IterationProgram:
    name: str
    correction: Branch
    saturated_original: bool = False


PROGRAMS = (
    IterationProgram('old-backward-conditional', Branch(POSITION, PC, Kind.CONDITIONAL)),
    IterationProgram('old-forward-conditional', Branch(POSITION, FORWARD, Kind.CONDITIONAL)),
    IterationProgram('old-not-taken-conditional', Branch(POSITION, PC + 3, Kind.CONDITIONAL, False)),
    IterationProgram('old-backward-direct', Branch(POSITION, BACKWARD, Kind.DIRECT)),
    IterationProgram('saturated-original', Branch(POSITION, PC, Kind.CONDITIONAL), True),
)


def loop_successor(count, pc, branch):
    if type(count) is not int or not 0 <= count <= MAX_ITERATIONS:
        raise ValueError('iteration count is outside the declared semantic range')
    if type(pc) is not int or not 0 <= pc < 1 << 49 or type(branch) is not Branch:
        raise ValueError('loop outcome requires a semantic source PC and branch')
    instruction = (pc // 8) * 8 + branch.position
    backward = instruction % (1 << TARGET_WIDTH) > branch.target % (1 << TARGET_WIDTH)
    extends = branch.kind is Kind.CONDITIONAL and branch.taken and backward
    return min(count + 1, MAX_ITERATIONS) if extends else 0


@dataclass(frozen=True, slots=True)
class IterationSnapshot:
    owner: object
    token_sequence: int
    pc: int
    count: int


@dataclass(frozen=True, slots=True)
class IterationStep:
    reference: object
    revision: int
    before: int
    after: int
    reason: str
    source: IterationSnapshot | None
    issue: bool


class LoopIterationReference:
    def __init__(self):
        self.revision = 0
        self.reset()

    def reset(self):
        self._cursor = 0
        self.owned = {}
        self.reasons = Counter()
        self.revision += 1
        self._proposal = None

    @property
    def cursor(self):
        return self._cursor

    def require(self, snapshot):
        if type(snapshot) is not IterationSnapshot or self.owned.get(snapshot.owner.sequence) is not snapshot:
            raise ValueError('iteration recovery needs an exact owned source in this reset epoch')
        return snapshot

    def snapshot(self, token):
        if type(token) is not Token:
            raise TypeError('iteration source must be an independently owned pipeline token')
        source = self.owned.get(token.history.sequence)
        if source is None or source.owner is not token.history or source.token_sequence != token.sequence or source.pc != token.pc:
            raise ValueError('iteration token does not own this source checkpoint')
        return source

    def retire(self, snapshot):
        self.require(snapshot)
        del self.owned[snapshot.owner.sequence]

    def preview(self, cycle, *, recovery=None):
        if type(cycle) is not Cycle:
            raise TypeError('iteration progression consumes autonomous pipeline events')
        first, second, third = cycle.tokens
        source, branch, reason = None, None, 'hold'
        if recovery is not None:
            if type(recovery) is not tuple or len(recovery) != 2:
                raise ValueError('iteration recovery requires an owned source and actual semantic correction')
            source, branch = recovery
            self.require(source)
            reason = 'backend'
        elif cycle.final_repair:
            source, branch, reason = self.snapshot(third), cycle.decisions[2].branch, 'final-repair'
        elif cycle.middle_repair:
            source, branch, reason = self.snapshot(second), cycle.decisions[1].branch, 'middle-repair'
        elif cycle.fires[1]:
            source, branch, reason = self.snapshot(first), cycle.decisions[0].branch, 'early'
        after = self.cursor if source is None else loop_successor(source.count, source.pc, branch)
        step = IterationStep(self, self.revision, self.cursor, after, reason, source, cycle.fires[0])
        self._proposal = step
        return step

    def apply(self, step, *, issued=None):
        if type(step) is not IterationStep or step is not self._proposal or step.reference is not self\
                or step.revision != self.revision or step.before != self.cursor:
            raise ValueError('iteration step was copied, stale, foreign or already applied')
        if step.source is not None:
            self.require(step.source)
        if step.issue != (issued is not None) or issued is not None and type(issued) is not Token:
            raise ValueError('one new iteration checkpoint belongs to each actual model issue')
        if issued is not None and issued.history.sequence in self.owned:
            raise ValueError('an iteration checkpoint cannot impersonate an existing prediction')
        snapshot = (None if issued is None else IterationSnapshot(
            issued.history, issued.sequence, issued.pc, step.after))
        self._cursor = step.after
        self.reasons[step.reason] += 1
        if snapshot is not None:
            self.owned[snapshot.owner.sequence] = snapshot
        self.revision += 1
        self._proposal = None
        return snapshot

    def advance(self, cycle, *, issued=None, recovery=None):
        return self.apply(self.preview(cycle, recovery=recovery), issued=issued)

    def state(self):
        return dict(cursor=self.cursor, revision=self.revision,
                    owned=tuple(self.owned.values()), reasons=dict(self.reasons))
