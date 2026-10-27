"""Owned prediction tokens, squash/replay and semantic history composition.

Only environment inputs enter Events. Stage occupancy, fires, repairs, PCs
and checkpoint words are outputs of this model, never observed state seeds.
The source-bank protocol is deliberately independent of signal sampling;
adapters must use owned predictor models. All-predictor adapters are not yet
complete: MicroOnlySources below explicitly rejects unsupported learning.
"""
from bpuverify.common.model.configuration import *

from dataclasses import dataclass, replace

from bpuverify.bpu.model.path_history import Checkpoint, PathHistoryReference, path_contribution
from bpuverify.bpu.model.selection import Choice, final_repair, middle_repair
from bpuverify.bpu.model.selection import Kind, StackAction


ENABLES = ('ubtb', 'abtb', 'mbtb', 'tage', 'sc', 'ittage', 'ras')


@dataclass(frozen=True, slots=True)
class Redirect:
    source: Checkpoint
    cfi_pc: int
    target: int
    taken: bool
    kind: Kind | None = None
    action: StackAction = StackAction.NONE

    def __post_init__(self):
        if type(self.source) is not Checkpoint or type(self.taken) is not bool:
            raise ValueError('redirect requires an owned checkpoint and semantic direction')
        if self.kind is not None and type(self.kind) is not Kind:
            raise ValueError('redirect kind must be a semantic branch kind')
        if type(self.action) is not StackAction:
            raise ValueError('redirect action must be a semantic stack operation')
        for value in (self.cfi_pc, self.target):
            if type(value) is not int or not 0 <= value < 1 << 49:
                raise ValueError('redirect is outside the current unguarded halfword address contract')


@dataclass(frozen=True, slots=True)
class Resolution:
    source: Checkpoint
    pc: int
    branches: tuple
    origin: 'Token | None' = None

    def __post_init__(self):
        if type(self.source) is not Checkpoint or type(self.pc) is not int or not 0 <= self.pc < 1 << 49:
            raise ValueError('resolution requires a checkpoint and unguarded halfword PC')
        if type(self.branches) is not tuple or len(self.branches) > 8:
            raise ValueError('resolution requires at most eight immutable branch slots')
        active = [branch for branch in self.branches if branch is not None]
        if any(type(branch) is not Outcome for branch in active):
            raise ValueError('resolution consumes semantic branch outcomes, not DUT payloads')
        if len({branch.position for branch in active}) != len(active) or sum(branch.mispredict for branch in active) > 1:
            raise ValueError('resolve positions must be unique with at most one misprediction')
        if self.origin is not None and (type(self.origin) is not Token
                or self.origin.history is not self.source or self.origin.pc!=self.pc):
            raise ValueError('resolution origin must own this exact PC/checkpoint')


@dataclass(frozen=True, slots=True)
class Outcome:
    position: int
    target: int
    kind: Kind
    taken: bool
    action: StackAction = StackAction.NONE
    mispredict: bool = False

    def __post_init__(self):
        if type(self.kind) is not Kind or type(self.action) is not StackAction or type(self.taken) is not bool or type(self.mispredict) is not bool:
            raise ValueError('resolved branch requires semantic kind/action/directions')
        if type(self.position) is not int or not 0 <= self.position < POSITIONS or type(self.target) is not int or not 0 <= self.target < 1 << 49:
            raise ValueError('resolved branch is outside the current position/address contract')


@dataclass(frozen=True, slots=True)
class Commit:
    source: 'Token'
    action: StackAction

    def __post_init__(self):
        if type(self.source) is not Token or type(self.action) is not StackAction:
            raise ValueError('commit requires an exact published token and semantic stack action')


@dataclass(frozen=True, slots=True)
class Events:
    reset_vector: int
    prediction_ready: bool = True
    metadata_ready: bool = True
    initialization_complete: bool = False
    enabled: tuple[bool, ...] = (True,) * len(ENABLES)
    redirect: Redirect | None = None
    feedback: Resolution | None = None
    reset: bool = False
    consumed_reset: bool | None = None
    # Most callers forecast the next edge. A passive acceptance receipt can
    # instead describe the edge just consumed; keep that clock contract explicit.
    feedback_at_edge: bool = False
    commit: Commit | None = None

    def __post_init__(self):
        if type(self.reset_vector) is not int or not 0 <= self.reset_vector < 1 << 49:
            raise ValueError('BPU pipeline currently requires an unguarded halfword reset PC')
        if type(self.enabled) is not tuple or len(self.enabled) != len(ENABLES):
            raise ValueError('BPU control requires seven immutable enable values')
        if any(type(value) is not bool for value in (*self.enabled, self.prediction_ready,
            self.metadata_ready, self.initialization_complete, self.reset,self.feedback_at_edge)):
            raise ValueError('BPU environment control values must be semantic bools')
        if self.redirect is not None and type(self.redirect) is not Redirect:
            raise ValueError('BPU recovery requires an owned semantic checkpoint')
        if self.feedback is not None and type(self.feedback) is not Resolution:
            raise ValueError('BPU feedback requires an associated semantic resolution')
        if self.consumed_reset is not None and type(self.consumed_reset) is not bool:
            raise ValueError('consumed reset must be a semantic bool or an unspecified logical clock boundary')
        if self.commit is not None and type(self.commit) is not Commit:
            raise ValueError('BPU retirement requires an owned semantic commit')


@dataclass(frozen=True, slots=True)
class Token:
    sequence: int
    pc: int
    history: Checkpoint
    lookup: object
    early: Choice | None = None
    middle: Choice | None = None
    middle_corrected: bool = False


@dataclass(frozen=True, slots=True)
class Cycle:
    tokens: tuple[Token | None, ...]
    decisions: tuple[Choice | None, ...]
    fires: tuple[bool, ...]
    flushes: tuple[bool, ...]
    middle_repair: bool
    final_repair: bool
    presented: tuple[Token, Choice] | None
    metadata: Token | None
    next_pc: int
    enabled: tuple[bool, ...]


class PipelineReference:
    """A source bank owns prediction/learning; this class owns token lifetime."""
    def __init__(self, sources):
        self.sources = sources
        # CSR DelayN is unconditional and is NOT reset with predictor state.
        self.control_pipe = [(False,) * len(ENABLES)] * 2
        self.control_samples = 0
        self.history = PathHistoryReference()
        self.sequence = 0
        self.reset(0)

    def reset(self, pc):
        self.history.reset()
        self.sources.reset()
        self.stages = (None, None, None)
        self.pc = pc
        self.initialized = False
        self.published = {}
        self.cycles = 0

    def checkpoint_for(self, metadata, *, source_pc=None):
        """Associate external encoding to owned, previously presented history.

        Equal encodings are not enough if complete logical histories differ.
        Such ambiguity requires an explicit verified source association (or a
        future complete FTQ owner/epoch adapter); never repair golden using
        the externally supplied low bits.
        """
        matches = [token.history for token in self.published.values()
                   if token.history.metadata() == metadata and (source_pc is None or token.pc == source_pc)]
        if not matches:
            raise ValueError('BPU metadata has no owned published source')
        if len({(item.history, item.taken_edges % PHR_STORAGE_BITS) for item in matches}) != 1:
            raise ValueError('BPU metadata aliases different history owners; full FTQ association required')
        return matches[0]

    def evaluate(self, events):
        enabled = self.control_pipe[-1]
        first, second, third = self.stages
        early = None if first is None else self.sources.choose(first, 1, enabled)
        middle = None if second is None else self.sources.choose(second, 2, enabled)
        late = None if third is None else self.sources.choose(third, 3, enabled)
        repair2 = second is not None and middle_repair(second.early, middle)
        repair3 = third is not None and final_repair(third.early, third.middle, late,
                                                   corrected_middle=third.middle_corrected)
        recovery = events.redirect is not None
        # S3 always retires, hence S2 has no downstream backpressure. Flush is
        # separate from transfer: a younger S1 can fire and still be squashed.
        consume1 = first is not None and events.prediction_ready
        consume2, consume3 = second is not None, third is not None
        flushes = (recovery or repair3 or repair2, recovery or repair3, recovery)
        issue = self.initialized and (first is None or consume1 or flushes[0])
        presented = ((third, late) if repair3 else (second, middle) if repair2
                     else (first, early) if first is not None else None)
        next_pc = (events.redirect.target if recovery else late.branch.target if repair3
                   else middle.branch.target if repair2 else early.branch.target if first is not None else self.pc)
        return Cycle(self.stages, (early, middle, late), (issue, consume1, consume2, consume3), flushes,
                     bool(repair2), bool(repair3), presented, third, next_pc, enabled)

    def advance(self, events):
        if type(events) is not Events:
            raise TypeError('BPU reference consumes semantic environment events')
        control = (events.enabled, self.control_pipe[0])
        if events.reset:
            self.control_samples += 1
            self.reset(events.reset_vector)
            self.control_pipe = list(control)
            return None
        if events.redirect is not None and not any(
                token.history is events.redirect.source for token in self.published.values()):
            raise ValueError('external redirect requires a published owned source')
        if events.feedback is not None and not any(token.history is events.feedback.source and token.pc == events.feedback.pc
                                                 for token in self.published.values()):
            raise ValueError('external feedback requires its published owned source PC')
        if events.feedback is not None and events.feedback.origin is not None and not any(
                token is events.feedback.origin for token in self.published.values()):
            raise ValueError('external feedback origin is not the exact published owner')
        if events.commit is not None:
            if not getattr(self.sources,'has_own_ras',False):
                raise NotImplementedError('FTQ commit requires the composed RAS source-bank adapter')
            if self.published.get(events.commit.source.sequence) is not events.commit.source:
                raise ValueError('external commit requires the exact published owner')
        cycle = self.evaluate(events)
        self.sources.validate(events, cycle)
        self.control_samples += 1
        first, second, third = self.stages
        early, middle, late = cycle.decisions
        if cycle.metadata is not None and events.redirect is None:
            token = cycle.metadata
            self.published[token.sequence] = token
        if events.redirect is not None:
            redirect = events.redirect
            transient = self.history.advance(taken=redirect.taken, cfi_pc=redirect.cfi_pc,
                                             target=redirect.target, restore=redirect.source)
            self.history.retire(transient)
        elif cycle.final_repair or cycle.middle_repair:
            token, decision = (third, late) if cycle.final_repair else (second, middle)
            transient = self.history.advance(taken=decision.branch.taken,
                cfi_pc=(token.pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS + decision.branch.position,
                target=decision.branch.target, restore=token.history)
            self.history.retire(transient)
        elif cycle.fires[1] and early.branch.taken:
            transient = self.history.advance(taken=True, cfi_pc=(first.pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS + early.branch.position,
                                             target=early.branch.target)
            self.history.retire(transient)
        issued = None
        if cycle.fires[0]:
            checkpoint = self.history.checkpoint()
            issued = Token(self.sequence, cycle.next_pc, checkpoint,
                           self.sources.capture(cycle.next_pc, checkpoint))
            self.sequence += 1
        next_third = (replace(second, middle=middle, middle_corrected=cycle.middle_repair)
                      if second is not None and not cycle.flushes[1] else None)
        next_second = replace(first, early=early) if cycle.fires[1] and not cycle.flushes[0] else None
        next_first = issued if issued is not None else None if cycle.fires[1] or cycle.flushes[0] else first
        # Predictor updates see the same pre-edge choices and accepted source.
        self.sources.advance(events, cycle, issued)
        retained = {id(token.history) for token in (*self.published.values(), next_first, next_second, next_third)
                    if token is not None}
        for token in (first, second, third):
            if token is not None and id(token.history) not in retained:
                self.history.retire(token.history)
        self.stages = next_first, next_second, next_third
        self._retain_sources()
        if first is not None or cycle.middle_repair or cycle.final_repair or events.redirect is not None:
            self.pc = cycle.next_pc
        elif not self.initialized:
            self.pc = events.reset_vector
        self.initialized |= events.initialization_complete
        self.control_pipe = list(control)
        self.cycles += 1
        return cycle

    def state(self):
        return dict(cycles=self.cycles, stages=self.stages, entry_pc=self.pc, initialized=self.initialized,
                    history=self.history.history, history_taken_edges=self.history.taken_edges,
                    published_contexts=len(self.published), enabled=self.control_pipe[-1])

    def lookup_history(self, events, cycle):
        """Pure pre-edge history view, including the winning correction.

        This predicts a future lookup's folds without changing state. Physical
        pending registers are neither read nor mirrored.
        """
        first, second, third = cycle.tokens
        early, middle, late = cycle.decisions
        if events.redirect is not None:
            request = events.redirect
            source, taken, pc, target = request.source, request.taken, request.cfi_pc, request.target
        elif cycle.final_repair or cycle.middle_repair:
            token, decision = (third, late) if cycle.final_repair else (second, middle)
            source, taken = token.history, decision.branch.taken
            pc, target = (token.pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS + decision.branch.position, decision.branch.target
        elif cycle.fires[1] and early.branch.taken:
            source, taken = Checkpoint(-1,self.history.history,self.history.taken_edges), True
            pc, target = (first.pc // ALIGN_HALFWORDS) * ALIGN_HALFWORDS + early.branch.position, early.branch.target
        else:
            return Checkpoint(-1,self.history.history,self.history.taken_edges)
        word = ((source.history * 4) ^ path_contribution(pc,target)) % (1 << PHR_STORAGE_BITS) if taken else source.history
        return Checkpoint(-1,word,source.taken_edges + int(taken))

    def retire_source(self, sequence):
        """FTQ owner explicitly releases a source; no arbitrary age eviction."""
        if sequence not in self.published:
            raise ValueError('BPU source was not published or was already retired')
        token = self.published[sequence]
        preflight = getattr(self.sources,'validate_release',None)
        if preflight is not None:
            preflight(token)
        del self.published[sequence]
        self.history.retire(token.history)
        self._retain_sources()

    def _retain_sources(self):
        retain = getattr(self.sources,'retain',None)
        if retain is not None:
            retain(tuple(self.published.values())+tuple(token for token in self.stages if token is not None))
