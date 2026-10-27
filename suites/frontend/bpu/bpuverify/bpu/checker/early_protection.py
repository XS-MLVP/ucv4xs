"""Source-owned protection, confirmed at the next full actual-state boundary."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from bpuverify.bpu.checker.early_opposition import EarlyOppositionChecks
from bpuverify.bpu.coverage.early_opposition import EarlyOppositionCoverage
from bpuverify.bpu.model.early_opposition import provider, resident, ahead_owner, main_counter, steady_history
from bpuverify.bpu.model.early_protection import Identity, ProtectionLedger, EDGES, guidance, rules, next_edge


class EarlyProtectionChecks(EarlyOppositionChecks):
    edge_definitions = EDGES
    preparation_coverage = EarlyOppositionCoverage
    record_taken = False

    def rule_names(self):
        return rules(self.mode, edges=self.edge_definitions)

    def closure_witness(self, rule):
        return {}

    def boundary_for(self, event):
        """Associate a semantic edge; specialized programs may require admission."""
        return next_edge(self.mode, self.confirmed, event, edges=self.edge_definitions)

    def __init__(self, coverage, mode, pc):
        if mode not in self.edge_definitions:
            raise ValueError('unknown protection boundary program')
        # Reuse semantic preparation checks. Their shared reached groups are
        # preparation evidence, not new checked credit for this boundary suite.
        super().__init__(self.preparation_coverage(), pc)
        self.boundaries, self.mode = coverage, mode
        self.identity = self.ledger = None
        self.pending = self.confirming_boundary = None
        self.actual_protection = None
        self.confirmed = {}
        self.completed = set()
        self.originals = {}
        self.lineage = deque(maxlen=4)
        self.redirect_count = 0
        self.last_redirect = self.redirect_source = None
        self.last_actual_tick = None

    def reach(self, rule, tick, **witness):
        self.boundaries.record(self.mode, 'reached', rule, tick, **witness)
        self.completed.add(rule)

    def remember(self, source):
        token = self.pipeline.source_token(source)
        self.originals.setdefault(source.meta_tick, (source, deepcopy(getattr(source, 'meta', None)),
                                                    self.pipeline.model.sources.short_snapshot(token)))
        return token

    def strong_negative(self, source):
        super().strong_negative(source)
        value = provider(self.pipeline.model.sources, self.remember(source))
        self.check((1, 0, 2), (value.table, value.counter, self.protected_useful),
                   'declared stable longest-history NT record, naturally allocated protection2')
        self.identity = Identity(value.table, value.index, value.tag, value.position)
        self.ledger = ProtectionLedger(counter=0, protection=2)
        self.reach('stable-original', source.meta_tick)

    def candidates(self, row, events, cycle, model, phase, previous):
        result = super().candidates(row, events, cycle, model, phase, previous)
        self.redirect_source = None if events.redirect is None else events.redirect.source
        self.redirect_ready = events.prediction_ready
        self.confirming_boundary = self.pending
        if self.identity is not None:
            values = row['observed']['early_direction']['useful']
            self.actual_protection = values[self.identity.table][self.identity.index]
        return result

    def checked(self, tick, *candidates):
        super().checked(tick, *candidates)
        self.last_actual_tick = tick
        if self.redirect_source is not None:
            self.redirect_count += 1
            self.last_redirect = tick, self.redirect_source, self.redirect_ready
        if self.identity is None:
            return
        if self.confirming_boundary is not None:
            written, event, edge = self.confirming_boundary
            self.check(written+2, tick, 'next lossless actual boundary, not expected-write credit')
            self.check(event.after, self.actual_protection, 'actual original protection after qualified guidance')
            if edge is not None:
                self.confirmed[edge] = event, written, tick
                self.reach(edge, tick, identity=asdict(self.identity), **asdict(event),
                           written_tick=written, actual_confirmation_tick=tick,
                           compared_protection_cells=1024)
                self.reach('complete-actual-state-confirmed', tick)
        self.pending = None
        self.check(self.ledger.protection, self.actual_protection, 'independent logical protection matches actual prestate')
        sources = self.pipeline.model.sources
        applied = self.applied
        if applied is not None:
            decision = guidance(applied.feedback, self.identity)
            if decision is not None:
                owner = next((owner for feedback, owner in self.offers if feedback is applied.feedback), None)
                self.check(True, owner is not None and sources is not None,
                           'qualified guidance retains its exact original S3 owner')
                self.check(True, self.pipeline.model.published.get(owner.sequence) is owner,
                           'guidance owner remains published, not a coincident equal payload')
                event = self.ledger.apply(owner.sequence, *decision)
                edge = self.boundary_for(event)
                if edge is not None:
                    self.reach('source-qualified-boundary', tick)
                self.pending = tick, event, edge
                self.lineage.append(dict(tick=tick, identity=self.identity, event=event, expected_edge=edge))
        self.check(False, sources.short.aged, 'no unrelated global aging in this boundary program')
        entry = resident(sources, self.identity.key)
        self.check((True, self.identity.tag, self.identity.position, self.ledger.counter),
                   (entry.valid, entry.tag, entry.position, entry.counter),
                   'same logical record and independently learned direction, never reallocation')
        self.check(self.ledger.protection, sources.short.useful[self.identity.table].get(self.identity.index, 0),
                   'cycle reference agrees with independent event ledger')

    def preserved_other_history(self, source, before):
        token = self.remember(source)
        sources = self.pipeline.model.sources
        self.check((3, True), (main_counter(token), steady_history(token, 2)),
                   'normal Main steering has a distinct stable taken history')
        self.check(False, steady_history(token, 4), 'different real program history from the protected NT path')
        if sources.snapshot(token).enabled:
            frame = sources.short_snapshot(token).prediction.frame
            self.check(True, frame is not None and frame.read.indices[self.identity.table] != self.identity.index,
                       'enabled alias lookup uses a distinct MicroTAGE record')
        self.check(before, (resident(sources, self.identity.key), self.ledger.protection),
                   'other-history preparation preserves original record and all protection')
        self.reach('other-history-isolation', source.meta_tick)

    def fresh_consumer(self, source):
        self.check(set(name for name, *_ in self.edge_definitions[self.mode]), set(self.confirmed),
                   'all declared boundary effects are actually confirmed before fresh consumption')
        token = self.remember(source)
        value = provider(self.pipeline.model.sources, token)
        last = max(row[2] for row in self.confirmed.values())
        self.check(True, source.prediction_tick > last, 'fresh original query follows the final actual boundary')
        self.check(True, value is not None and (value.key, value.tag, value.position)==
                   (self.identity.key, self.identity.tag, self.identity.position)
                   and (value.counter >= 4) == self.record_taken,
                   'fresh complete public consumer retains original identity and declared direction')
        self.reach('fresh-original-consumer', source.meta_tick, owner=token.sequence,
                   prediction_tick=source.prediction_tick, identity=asdict(self.identity))

    def finish_boundaries(self, owners):
        self.check(None, self.pending, 'all learning has crossed its actual comparison boundary')
        for source, metadata, snapshot in self.originals.values():
            token = self.pipeline.source_token(source)
            self.check(metadata, getattr(source, 'meta', None), 'original actual metadata remains immutable')
            self.check(snapshot, self.pipeline.model.sources.short_snapshot(token), 'original query frame remains immutable')
        tick = max(self.last_actual_tick or 0,
                   max((source.meta_tick for source, _, _ in self.originals.values()), default=0))
        self.reach('original-snapshots-immutable', tick)
        self.check(set(self.rule_names()), self.completed, 'all declared semantic boundary requirements complete')
        self.check(False, self.pipeline.model.sources.main_pending(), 'normal owned Main learning is drained')
        for source in {source.meta_tick: source for source in
                       (*owners, self.cold, self.original, self.fallback, self.consumer, self.strong)}.values():
            if source.meta_tick in self.pipeline.source_receipts:
                self.pipeline.retire_source(source.meta_tick)
        for rule in self.rule_names():
            witness = dict(self.closure_witness(rule))
            if rule in self.confirmed:
                event, written, actual = self.confirmed[rule]
                witness.update(dict(identity=asdict(self.identity), **asdict(event), written_tick=written,
                                    actual_confirmation_tick=actual, compared_protection_cells=1024))
            self.boundaries.record(self.mode, 'checked', rule, tick, **witness)
