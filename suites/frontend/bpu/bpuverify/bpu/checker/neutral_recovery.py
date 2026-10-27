"""Only a declared, bounded original can close a neutral-recovery edge."""
from copy import deepcopy
from dataclasses import asdict
from bpuverify.bpu.checker.early_positive_protection import EarlyPositiveProtectionChecks
from bpuverify.bpu.checker.early_short_protection import EarlyShortProtectionChecks
from bpuverify.bpu.model.early_opposition import provider, resident
from bpuverify.bpu.model.neutral_recovery import EDGES, STEPS, rules


class Checks(EarlyPositiveProtectionChecks):
    edge_definitions = EDGES
    optional_rules = frozenset(('parallel-long-allocation', 'fresh-long-consumer',
        'neutral-seed-confirmed', 'neutral-direction-strength', 'weak-T-seed-preserved'))

    def __init__(self, coverage, profile, pc):
        super().__init__(coverage, profile, pc)
        self.armed = None; self.owned = {}; self.optional = {}; self.final = None

    def rule_names(self): return rules(self.mode)
    @property
    def requires_parallel_allocation(self): return False

    def reach(self, rule, tick, **witness):
        if rule in self.rule_names(): return super().reach(rule, tick, **witness)
        if rule not in self.optional_rules: raise ValueError('undeclared integrated-neutral rule: '+rule)
        self.optional[rule] = dict(tick=tick, **deepcopy(witness))

    def seed_ready(self):
        self.check((4, 1), (self.ledger.counter, self.ledger.protection), 'normal weak T seed remains before the declared program')
        if self.mode == 'neutral-lower': self.reach('weak-T-seed-preserved', self.last_actual_tick)

    def arm(self, name):
        self.check(None, self.armed, 'one declared neutral edge in flight')
        self.check(None, self.pending, 'earlier guidance crossed its actual comparison')
        short = self.pipeline.model.sources.short
        self.check((None, None), (short.offered, short.learning), 'old FastTrain work drained before new phase admission')
        step = STEPS[self.mode][len(self.confirmed)]
        self.check(step.name, name, 'semantic stages are declared in order, not selected from actual results')
        self.check((step.counter_before, step.before), (self.ledger.counter, self.ledger.protection),
            'predeclared direction confidence and protection before driving the source window')
        self.armed = name

    def boundary_for(self, event):
        if self.armed is None: return None
        step = next(step for step in STEPS[self.mode] if step.name == self.armed)
        self.check(step.signature, (event.kind, event.counter_before, event.counter_after, event.before, event.after),
            'first qualified original in the admitted phase has the exact declared semantic effect')
        self.check(True, self.selected is not None and event.owner == self.selected.sequence,
            'phase belongs to the exact bounded S1 original, not preparation or another equal-PC source')
        return self.armed

    def checked(self, tick, *candidates):
        previous = self.pending
        super().checked(tick, *candidates)
        if previous is not None and previous[2] is not None:
            self.check(previous[2], self.armed, 'actual next-boundary confirmation closes the admitted edge')
            self.armed = None

    def owned_edge(self, name, source):
        self.check(None, self.armed, 'actual effect confirmation precedes original receipt closure')
        step = next(step for step in STEPS[self.mode] if step.name == name)
        event, written, actual = self.confirmed[name]
        token = self.remember(source); value = provider(self.pipeline.model.sources, token)
        self.check(event.owner, token.sequence, 'actual learning owner and complete public S3 receipt are the same original')
        self.check(step.counter_before, value.counter, 'original provider confidence is not replaced by the current result')
        if step.base is not None:
            self.check(step.base, value.base, 'original base determines neutral agreement or genuine contribution')
        self.check(True, source.meta_tick < written < actual and actual == written+2,
            'original response, real learning and full actual-state confirmation are distinct ordered facts')
        self.owned[name] = dict(owner=token.sequence, prediction_tick=source.prediction_tick,
            meta_tick=source.meta_tick, written_tick=written, actual_confirmation_tick=actual,
            original_provider=asdict(value), effect=asdict(event))

    def fresh_consumer(self, source):
        super().fresh_consumer(source)
        value = provider(self.pipeline.model.sources, self.pipeline.source_token(source))
        step = STEPS[self.mode][-1]
        self.check(step.counter_after, value.counter, 'fresh public original consumes the named final direction result before its own feedback')
        self.final = dict(prediction_tick=source.prediction_tick, meta_tick=source.meta_tick,
            owner=self.pipeline.source_token(source).sequence, provider=asdict(value))

    def finish_boundaries(self, owners):
        self.check(None, self.armed, 'no unconfirmed admitted edge')
        self.check({step.name for step in STEPS[self.mode]}, set(self.owned), 'every named effect has its exact original source receipt')
        for step in STEPS[self.mode]:
            event, written, actual = self.confirmed[step.name]
            self.check(step.signature, (event.kind, event.counter_before, event.counter_after, event.before, event.after),
                'all declared neutral/recovery effects retain independent semantics')
            self.check(event.owner, self.owned[step.name]['owner'], 'no original effect rebinding at closure')
        self.check(True, self.final is not None, 'fresh final original consumer required')
        seed = self.original_seed; sources = self.pipeline.model.sources
        self.check(True, seed is not None and self.pipeline.model.published.get(seed.owner.sequence) is seed.owner,
            'normal T seed remains the original published owner')
        self.check(seed.snapshot, sources.short_snapshot(seed.owner), 'original T allocation snapshot remains immutable')
        if self.mode == 'neutral-upper':
            self.check([(4,5), (5,6), (6,7)], [(event.counter_before, event.counter_after)
                for event, _, _ in self.neutral_confirmations[:3]], 'direction prepared by three real consistent sources, not protection rewards')
        for rule in ('explicit-neutral-source', 'neutral-does-not-lock-learning', 'owned-edge-receipts',
                     'full-preservation-and-seed-immutable'):
            self.reach(rule, self.last_actual_tick, owned=deepcopy(self.owned), final=deepcopy(self.final))
        EarlyShortProtectionChecks.finish_boundaries(self, owners)
        self.boundaries.finish(self.mode)

    def snapshot(self):
        return deepcopy(dict(profile=self.mode, armed=self.armed, owned=self.owned, final=self.final,
            identity=None if self.identity is None else asdict(self.identity),
            current=None if self.ledger is None else dict(counter=self.ledger.counter, protection=self.ledger.protection),
            optional=self.optional, full_FTQ_source_eligibility_proved=False))
