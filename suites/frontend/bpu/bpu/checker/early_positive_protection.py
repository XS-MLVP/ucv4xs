from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""Positive-source preparation plus the existing original-record strength ledger.

The two existing checkers are cooperative: source preparation freezes T seeds;
the short-record checker owns actual issue windows and protection confirmation.
No RTL state is used to seed either reference.
"""
from dataclasses import asdict

from suites.frontend.bpu.bpu.checker.early_positive import EarlyPositiveChecks
from suites.frontend.bpu.bpu.checker.early_short_protection import EarlyShortProtectionChecks
from suites.frontend.bpu.bpu.coverage.early_positive import EarlyPositiveCoverage
from suites.frontend.bpu.bpu.model.early_opposition import provider, resident, ahead_owner, main_counter, steady_history
from suites.frontend.bpu.bpu.model.early_positive_protection import EDGES, rules
from suites.frontend.bpu.bpu.model.early_protection import Identity, ProtectionLedger


class EarlyPositiveProtectionChecks(EarlyShortProtectionChecks, EarlyPositiveChecks):
    edge_definitions = EDGES
    preparation_coverage = EarlyPositiveCoverage
    record_taken = True
    seed_table, seed_protection = 0, 1

    def __init__(self, coverage, mode, pc):
        super().__init__(coverage, mode, pc)
        self.original_seed = None
        self.neutral_confirmations = []

    def rule_names(self):
        return rules(self.mode)

    def seed_candidates(self):
        return [(key, seed, entry, useful) for key, (seed, entry, useful)
                in self.protected_positive.items() if key[0] == self.seed_table]

    def arm_seed(self):
        self.check(None, self.identity, 'one declared original T identity before driving')
        self.check(True, self.positive_prepared is not None, 'normal owned positive preparation completed')
        candidates = self.seed_candidates()
        self.check(1, len(candidates), 'one independently predeclared original T record, never an actual-selected hit')
        key, seed, entry, useful = candidates[0]
        self.check((4, self.seed_protection), (entry.counter, useful), 'normal T allocation, not transplanted table initial state')
        self.check(True, seed.compared is not None and seed.compared == seed.written+2,
                   'original T allocation crossed its complete actual comparison')
        sources = self.pipeline.model.sources
        self.check(entry, resident(sources, key), 'declared T identity is still resident before its new program')
        self.check(self.seed_protection, sources.short.useful[self.seed_table].get(key[1], 0),
                   'original T protection preserved during Main-only preparation')
        self.identity = self.intended = Identity(self.seed_table, key[1], entry.tag, entry.position)
        self.ledger = ProtectionLedger(counter=4, protection=self.seed_protection)
        self.original_seed, self.seeded = seed, True
        self.reach('confirmed-T-seed', self.positive_prepared.meta_tick, identity=asdict(self.identity),
                   owner=seed.owner.sequence, written_tick=seed.written, actual_confirmation_tick=seed.compared)

    @property
    def requires_parallel_allocation(self):
        return self.mode in ('upper-release', 'lower-recover')

    def open_original(self, *, longer=False, expect_taken=None):
        self.check(True, self.original_seed is not None, 'T record must be declared before opening a source window')
        return super().open_original(longer=longer, expect_taken=expect_taken)

    def preserved_base_bias(self, source, before, taken):
        token = self.remember(source); sources = self.pipeline.model.sources
        self.check((3 if taken else 0, True), (main_counter(token), steady_history(token, 2 if taken else FALLBACK)),
                   'normal base learning has its own stable direction history')
        self.check(3 if taken else 0, ahead_owner(sources, token)[1], 'same normal Ahead owner reached the declared base direction')
        value = provider(sources, token)
        self.check(True, value is None or (value.key, value.tag) != (self.identity.key, self.identity.tag),
                   'base preparation does not consume the protected original T identity')
        self.check(before, (resident(sources, self.identity.key), self.ledger.protection),
                   'base history preserves the complete original record and protection')
        self.reach('other-history-isolation', source.meta_tick)
        if self.mode == 'direction-return' and taken:
            self.check((4, 1), (self.ledger.counter, self.ledger.protection),
                       'weak original T seed preserved, not strengthened before crossing direction')
            self.reach('weak-T-seed-preserved', source.meta_tick, identity=asdict(self.identity))

    def checked(self, tick, *candidates):
        previous = self.pending
        super().checked(tick, *candidates)
        if previous is not None:
            written, event, _ = previous
            if (self.mode != 'direction-return' and 'neutral-direction-strength' not in self.completed
                    and event.kind == 'neutral' and event.before == event.after == self.seed_protection
                    and event.counter_before < event.counter_after <= 7):
                self.neutral_confirmations.append((event, written, tick))
                if event.counter_after == 7:
                    self.check([(4, 5), (5, 6), (6, 7)],
                        [(e.counter_before, e.counter_after) for e, _, _ in self.neutral_confirmations],
                        'three distinct consistent sources strengthen T without earning protection')
                    self.reach('neutral-direction-strength', tick, identity=asdict(self.identity),
                        compared_protection_cells=1024,
                        events=[dict(**asdict(e), written_tick=w, actual_confirmation_tick=a)
                                for e, w, a in self.neutral_confirmations])

    def finish_boundaries(self, owners):
        if self.mode == 'direction-return':
            self.check([('penalty',4,3,1,0), ('penalty',3,4,0,0), ('reward',4,5,0,1)],
                [(self.confirmed[name][0].kind, self.confirmed[name][0].counter_before,
                  self.confirmed[name][0].counter_after, self.confirmed[name][0].before, self.confirmed[name][0].after)
                 for name, *_ in EDGES[self.mode] if name in self.confirmed],
                'T error, NT error and qualified T reward keep distinct actual source meanings')
            self.check([], self.neutral_confirmations, 'weak seed is not silently strengthened before direction crossing')
        else:
            self.check(True, bool(self.neutral_confirmations), 'actual consistent guidance established direction independently of protection')
        seed = self.original_seed; sources = self.pipeline.model.sources
        self.check(True, seed is not None and sources is not None, 'original T seed remains owned')
        self.check(True, self.pipeline.model.published.get(seed.owner.sequence) is seed.owner,
                   'original T allocation owner has not been substituted')
        self.check(seed.snapshot, sources.short_snapshot(seed.owner), 'initial T learning snapshot remains immutable')
        super().finish_boundaries(owners)
