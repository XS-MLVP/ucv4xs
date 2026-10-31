"""Owned query history through an ordered speculative window journal.

Journal positions are logical prediction ages, not circular hardware cells.
Read views and feedback views are distinct: recovery may repair a young
metadata view after its weight read, but published views cannot be rebound.
Only independently predicted pipeline events enter this model.
"""
from suites.frontend.bpu.models.configuration import *

from collections import Counter
from dataclasses import dataclass, replace

from suites.frontend.bpu.bpu.model.common_history import Block, Value
from suites.frontend.bpu.bpu.model.loop_iteration import LoopIterationReference, PROGRAMS
from suites.frontend.bpu.bpu.model.pipeline import Cycle, Token
from suites.frontend.bpu.bpu.model.selection import Branch
from suites.frontend.bpu.sc.transaction.types import ScHistory

PROFILES = tuple(program.name for program in PROGRAMS) + (
    'two-condition-prefix-direct-recovery', 'final-direction-repair')
COMMON_RULES = ('own-history-at-query', 'original-public-history', 'held-source-preserved',
                'young-replacement-history', 'restore-executed-prefix', 'published-original-immutable')
RULES = {profile: COMMON_RULES + (
    ('restore-read-vs-feedback-view',) if profile in ('old-forward-conditional', 'old-not-taken-conditional',
        'two-condition-prefix-direct-recovery') else
    ('late-replay-origin',) if profile == 'final-direction-repair' else ()) for profile in PROFILES}


@dataclass(frozen=True, slots=True)
class QueryHistory:
    owner: object
    sequence: int
    pc: int
    block: Block
    read: Value
    metadata: Value
    loop: int
    published: bool = False


@dataclass(frozen=True, slots=True)
class QueryHistoryStep:
    reference: object
    revision: int
    cycle: Cycle
    lookup: Value
    completed: Value | None
    recovered: Value | None
    recovery: object
    iteration: object
    reason: str


class CommonQueryReference:
    def __init__(self):
        self.iterations = LoopIterationReference()
        self.revision = 0
        self.reset()

    def reset(self):
        self.value = Value()
        self.journal, self.sources = {}, {}
        self.next_issue = self.next_complete = self.prediction_origin = self.replay_origin = 0
        self.young_history = self.middle_history = Value()
        self.pending = None
        self.reasons = Counter()
        self.iterations.reset()
        self.revision += 1
        self._proposal = None

    def snapshot(self, token):
        if type(token) is not Token:
            raise TypeError('query history requires an independently owned pipeline token')
        source = self.sources.get(token.history.sequence)
        if source is None or source.owner is not token.history or source.sequence != token.sequence or source.pc != token.pc:
            raise ValueError('query history is absent, retired or belongs to another original')
        return source

    def source_for(self, owner):
        source = self.sources.get(owner.sequence)
        if source is None or source.owner is not owner:
            raise ValueError('query history requires the exact original checkpoint')
        return source

    def sc_history(self, token, *, feedback=False):
        source = self.snapshot(token)
        if feedback and not source.published:
            raise ValueError('SC feedback history needs a published original')
        value = source.metadata if feedback else source.read
        return ScHistory(source.owner.history % (1 << PHR_BITS), value.ghr, value.bw, source.loop, value.valid)

    def retire(self, token):
        source = self.snapshot(token)
        if self.pending is not None and self.pending[0].owner is source.owner:
            raise ValueError('a pending recovery still owns this query history')
        self.iterations.retire(self.iterations.snapshot(token))
        del self.sources[source.owner.sequence]

    def preview(self, cycle, *, recovery=None):
        if type(cycle) is not Cycle:
            raise TypeError('query history consumes autonomous pipeline events')
        if recovery is not None:
            source, branch = recovery
            if type(source) is not QueryHistory or self.source_for(source.owner) is not source or not source.published:
                raise ValueError('query recovery needs its exact published original')
            if type(branch) is not Branch:
                raise TypeError('query recovery needs a semantic branch outcome')
        third = cycle.metadata
        completed = (None if third is None else self.value.append(
            Block.from_token(third).outcomes(cycle.decisions[2].branch), valid=True))
        recovered = (None if self.pending is None else self.pending[0].metadata.append(
            self.pending[0].block.outcomes(self.pending[1], recovering=True), valid=False))
        if recovery is not None:
            lookup, reason = replace(recovery[0].metadata, valid=False), 'backend-placeholder'
        elif recovered is not None:
            lookup, reason = recovered, 'backend-prefix'
        elif cycle.final_repair:
            lookup, reason = self.journal.get(self.replay_origin, Value()), 'final-replay'
        elif cycle.middle_repair:
            lookup, reason = self.young_history, 'middle-reuse'
        elif cycle.fires[0] and completed is not None and self.prediction_origin == self.next_complete:
            lookup, reason = completed, 'completed-forward'
        elif cycle.fires[0]:
            lookup, reason = self.journal.get(self.prediction_origin, Value()), 'window-read'
        else:
            lookup, reason = Value(), 'no-query'
        loop_recovery = (None if recovery is None else (
            self.iterations.owned[recovery[0].owner.sequence], recovery[1]))
        iteration = self.iterations.preview(cycle, recovery=loop_recovery)
        step = QueryHistoryStep(self, self.revision, cycle, lookup, completed, recovered,
                                recovery, iteration, reason)
        self._proposal = step
        return step

    def _metadata(self, token, value):
        source = self.snapshot(token)
        if source.published and source.metadata != value:
            raise AssertionError('a published history view cannot be rewritten')
        self.sources[token.history.sequence] = replace(source, metadata=value)

    def apply(self, step, *, issued=None):
        if type(step) is not QueryHistoryStep or step is not self._proposal or step.reference is not self or step.revision != self.revision:
            raise ValueError('query history step was stale, copied, foreign or already consumed')
        cycle = step.cycle
        if cycle.fires[0] != (issued is not None) or issued is not None and type(issued) is not Token:
            raise ValueError('each actual query issue needs its exact new token')
        if issued is not None and issued.history.sequence in self.sources:
            raise ValueError('a query cannot impersonate an existing original')
        first, second, third = cycle.tokens
        old_replay = self.replay_origin
        replay_ready = self.replay_origin + 2 == self.next_complete
        if step.recovery is not None:
            self.journal[self.next_complete] = Value()
            self.journal[self.next_complete - 1] = step.lookup
            self.next_issue = self.next_complete + 1
            self.prediction_origin = self.replay_origin = self.next_complete - 1
        elif cycle.final_repair:
            self.journal[self.next_complete] = step.completed
            self.journal[self.next_complete + 1] = Value()
            self.next_issue = self.next_complete + 2
            self.prediction_origin = self.replay_origin = self.replay_origin + int(replay_ready)
            self.next_complete += 1
        elif cycle.middle_repair:
            next_complete = self.next_complete + int(step.completed is not None)
            if step.completed is not None:
                self.journal[self.next_complete] = step.completed
            self.journal[next_complete + 1] = Value()
            self.next_issue = next_complete + 2
            self.replay_origin += int(step.completed is not None and replay_ready)
            self.next_complete = next_complete
        else:
            if issued is not None:
                advance_origin = self.next_issue - self.prediction_origin == 3
                self.journal[self.next_issue] = Value()
                self.next_issue += 1
                self.prediction_origin += int(advance_origin)
            if step.completed is not None:
                self.journal[self.next_complete] = step.completed
                self.next_complete += 1
                self.replay_origin += int(replay_ready)
        if step.recovered is not None:
            self.journal[old_replay] = step.recovered
        if third is not None:
            self.sources[third.history.sequence] = replace(self.snapshot(third), published=True)
        if second is not None and not cycle.flushes[1]:
            self._metadata(second, self.middle_history)
        if first is not None and cycle.fires[1] and not cycle.flushes[0]:
            self._metadata(first, step.recovered if step.recovered is not None else self.young_history)
        elif first is not None and not cycle.flushes[0] and step.recovered is not None:
            self._metadata(first, step.recovered)
        if cycle.fires[1]:
            self.middle_history = self.young_history
        if issued is not None:
            self.young_history = step.lookup
            self.sources[issued.history.sequence] = QueryHistory(issued.history, issued.sequence, issued.pc,
                Block.from_token(issued), step.lookup, step.lookup, step.iteration.after)
        if step.recovered is not None:
            self.young_history = self.middle_history = step.recovered
            self.value = step.recovered
        elif step.completed is not None:
            self.value = step.completed
        self.pending = step.recovery
        self.iterations.apply(step.iteration, issued=issued)
        self.reasons[step.reason] += 1
        self.revision += 1
        self._proposal = None
        return None if issued is None else self.snapshot(issued)

    def state(self):
        return dict(value=self.value, next_issue=self.next_issue, next_complete=self.next_complete,
            prediction_origin=self.prediction_origin, replay_origin=self.replay_origin,
            pending=self.pending, sources=len(self.sources), reasons=dict(self.reasons),
            iteration=self.iterations.cursor, revision=self.revision)
