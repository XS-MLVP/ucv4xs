"""Owned integrated guidance, independent event counts and complete aging effects."""
from dataclasses import dataclass
from collections import deque

from suites.frontend.bpu.bpu.checker.early_positive import EarlyPositiveChecks
from suites.frontend.bpu.bpu.coverage.early_aging import AGE_RULES, RULES
from suites.frontend.bpu.bpu.model.early_aging import FailureLedger, allocation, aged
from suites.frontend.bpu.bpu.model.early_opposition import provider, stable_negative, steady_history, CONDITIONAL, FALLBACK


@dataclass(frozen=True, slots=True)
class Guidance:
    token: object
    snapshot: object
    feedback: object


def all_protection(values):
    return tuple(tuple(table.get(index, 0) for index in range(512)) for table in values)


def sparse(values):
    return {f'{table}.{index}': value for table, row in enumerate(values)
            for index, value in enumerate(row) if value}


class EarlyAgingChecks(EarlyPositiveChecks):
    completion_rules = RULES

    def __init__(self, coverage, pc):
        super().__init__(coverage, pc)
        self.ledger = FailureLedger()
        self.offered = self.processing = None
        self.decision = None
        self.samples = 0
        self.next_must_be_empty = None
        self.current = self.current_decision = self.read_decision = None
        self.age_before = self.confirm_age = None
        self.age_tick = None
        self.history_seeds = {}
        self.consumers = {}
        self.backend = set()
        self.lineage = deque(maxlen=4)

    def check(self, expected, actual, point):
        return super().check(expected, actual, dict(point=point,
            failures=self.ledger.failures, count=self.ledger.count, ages=self.ledger.ages,
            processing=None if self.processing is None else self.processing.token.sequence))

    def seed_history(self, source, taken):
        self.check(False, taken in self.history_seeds, 'one original seed per semantic history')
        token = self.pipeline.source_token(source)
        sources = self.pipeline.model.sources
        value = provider(sources, token)
        self.check(True, value is not None and (value.counter >= 4) == taken,
                   'seed is an independently learned real provider')
        self.check(True, steady_history(token, CONDITIONAL if taken else FALLBACK), 'seed owns its stable path history')
        if not taken:
            self.check(True, stable_negative(sources, token), 'strong original negative provider')
        self.history_seeds[taken] = (source, sources.short_snapshot(token), value)

    def resolved(self, source, event):
        tick, resolution = event
        self.check(False, source.meta_tick in self.backend, 'no repeated backend source')
        self.check(True, resolution.origin is self.pipeline.source_token(source) and tick > source.meta_tick,
                   'actual feedback belongs to its original published source')
        self.backend.add(source.meta_tick)

    def candidates(self, row, events, cycle, model, phase, previous):
        result = super().candidates(row, events, cycle, model, phase, previous)
        self.samples += 1
        sources = model.sources
        actual = row['observed']['early_direction']
        read = sources.short.read
        frame = sources.short.frame
        self.lineage.append(dict(sample=self.samples, read=read, frame=frame,
            retained=tuple(dict(table=table, index=index,
                newest=sources.short.updates[table].newest(index),
                committed=sources.short.memory[table].get(index))
                for table, index in enumerate((0, 0) if read is None else read.indices))))
        control = actual['maintenance']
        self.check(self.ledger.count, control['low'], 'numeric counter follows qualified learning events only')
        self.check((int(self.processing is not None),) + (int(self.ledger.aging),) * 2,
                   (control['fire'],) + tuple(table['age'] for table in control['tables']),
                   'real registered learning and shared maintenance opportunity')
        expected_feedback = None if self.processing is None else self.processing.feedback
        model_feedback = None if sources.short.learning is None else sources.short.learning.feedback
        self.check(expected_feedback, model_feedback, 'event-ledger learning owns the original guidance')
        self.current_decision = self.decision
        if self.decision is not None:
            self.check((int(self.decision.wrong_position is not None), self.decision.mask),
                       (control['need'], control['mask']), 'independently qualified need and longer-table candidate')
        if self.next_must_be_empty is not None:
            self.check((None, 0), (cycle.metadata, actual['fast']['valid']),
                       dict(younger_path_cancelled_after=self.next_must_be_empty))
        self.current = None
        token = cycle.metadata
        if token is not None:
            feedback = sources.short_feedback(token, cycle.decisions[2])
            if feedback is not None:
                self.current = Guidance(token, sources.short_snapshot(token), feedback)
        self.read_decision = None
        if self.offered is not None and cycle.enabled[1] and events.initialization_complete:
            feedback = self.offered.feedback
            protection = tuple(sources.short.useful[table].get(index, 0)
                for table, index in enumerate(feedback.indices))
            self.read_decision = allocation(feedback, protection)
        self.age_before = None
        if self.ledger.aging:
            self.check(None, self.processing, 'this coherent parent program has no adjacent ghost learning at maintenance')
            self.check((0, 0, 0, 0), tuple(value for table in control['tables']
                for value in (table['allocate'], table['update'])), 'no actual write command from cancelled younger guidance')
            self.age_before = all_protection(sources.short.useful)
        if self.confirm_age is not None:
            expected_sample, expected_state = self.confirm_age
            self.check(expected_sample, self.samples, 'immediate complete post-maintenance observation')
            self.check(sparse(expected_state), sparse(actual['useful']), 'all 1024 cells age from the common prestate')
        return result

    def checked(self, tick, *candidates):
        super().checked(tick, *candidates)
        if self.next_must_be_empty is not None:
            self.mark(AGE_RULES[2], tick)
        self.next_must_be_empty = None
        if self.current is not None:
            decision = allocation(self.current.feedback, (0, 0))
            if decision.wrong_position is not None:
                self.next_must_be_empty = self.current.token.sequence
        if self.current_decision is not None and self.current_decision.wrong_position is not None:
            if self.current_decision.failed:
                if self.current_decision.provider == 1:
                    self.mark(AGE_RULES[0], tick)
                else:
                    self.mark(AGE_RULES[8], tick)
            else:
                self.mark(AGE_RULES[1], tick)
        if self.confirm_age is not None:
            self.mark(AGE_RULES[5], tick)
        self.confirm_age = None
        if self.age_before is not None:
            self.check(None, self.age_tick, 'one qualified maintenance window')
            self.age_tick = tick
            self.mark(AGE_RULES[3], tick)
            self.mark(AGE_RULES[4], tick)
            self.confirm_age = (self.samples + 1, aged(self.age_before))
        self.ledger.apply(self.current_decision)
        self.processing = self.offered if self.read_decision is not None else None
        self.decision = self.read_decision
        self.offered = self.current

    def consumed(self, source, taken):
        self.check(True, self.age_tick is not None and self.confirm_age is None, 'maintenance and actual full-state comparison precede consumers')
        self.check(False, taken in self.consumers, 'one fresh post-maintenance consumer per history')
        self.check(True, source.prediction_tick > self.age_tick, 'consumer request really follows maintenance')
        original, snapshot, seed = self.history_seeds[taken]
        token = self.pipeline.source_token(source)
        sources = self.pipeline.model.sources
        value = provider(sources, token)
        self.check(True, value is not None and (value.counter >= 4) == taken, 'learned direction remains publicly consumable')
        self.check((seed.key, seed.tag, seed.position), (value.key, value.tag, value.position), 'same original branch/history provider identity')
        self.check(snapshot, sources.short_snapshot(self.pipeline.source_token(original)), 'original history source remains immutable')
        self.consumers[taken] = source
        if len(self.consumers) == 2:
            self.mark(AGE_RULES[6], source.meta_tick)

    def finish_aging(self, additional_sources=()):
        self.check({False, True}, set(self.history_seeds), 'both independently established histories')
        self.check({False, True}, set(self.consumers), 'both new public provider consumers')
        self.check((1, None), (self.ledger.ages, self.confirm_age), 'one fully compared maintenance event')
        self.check(True, self.ledger.failures >= 128 and self.ledger.successes > 0,
                   'real failure threshold and discriminating successful learning')
        for original, snapshot, _ in self.history_seeds.values():
            self.check(snapshot, self.pipeline.model.sources.short_snapshot(self.pipeline.source_token(original)), 'no original seed rebase')
        tick = max(source.meta_tick for source in self.consumers.values())
        self.mark(AGE_RULES[7], tick)
        super().finish_positive(additional_sources, completion_tick=tick)
