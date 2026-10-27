"""Confirm longest-provider strength and independent no-candidate accounting."""
from dataclasses import asdict

from bpuverify.bpu.checker.early_positive_protection import EarlyPositiveProtectionChecks
from bpuverify.bpu.model.early_aging import FailureLedger
from bpuverify.bpu.model.early_protection import guidance, Identity, ProtectionLedger
from bpuverify.bpu.model.early_opposition import provider, resident
from bpuverify.bpu.model.early_long_positive_protection import EDGES, FREE_SHORT_MODES, rules, intended_identity


class EarlyLongPositiveProtectionChecks(EarlyPositiveProtectionChecks):
    edge_definitions = EDGES
    seed_table, seed_protection = 1, 2
    provider_rule = 'long-not-short-provider'

    def __init__(self, coverage, mode, pc):
        super().__init__(coverage, mode, pc)
        self.failure_ledger = FailureLedger()
        self.failure_pending = None
        self.confirmed_failures = []
        self.short_identity = self.short_ledger = self.short_seed = None
        self.short_window = self.short_selected = self.short_pending = None
        self.short_release = self.short_consumer = None
        self.available_errors = []
        self.available_pending = None
        self.short_receipts = {}
        self.restored_taken = None

    def arm_seed(self):
        # Both identities come from confirmed independent allocation, before
        # any later source is driven. The protected long owner never changes.
        rows = [(key, seed, entry, useful) for key, (seed, entry, useful)
                in self.protected_positive.items() if key[0] == 0]
        self.check(1, len(rows), 'one independently declared companion short identity')
        key, seed, entry, useful = rows[0]
        self.check((4, 1, seed.written+2), (entry.counter, useful, seed.compared),
                   'companion short seed has its own actual allocation confirmation')
        super().arm_seed()
        self.short_identity = Identity(0, key[1], entry.tag, entry.position)
        self.short_ledger = ProtectionLedger(counter=4, protection=1)
        self.short_seed = seed

    def open_original(self, **kwargs):
        accepted = super().open_original(**kwargs)
        self.short_window = None
        return accepted

    def open_short(self, *, preserve=False):
        self.check(True, self.mode in FREE_SHORT_MODES, 'companion proof belongs to a no-backward-allocation program')
        self.check((6, 0) if preserve else (7, 1),
                   (self.short_ledger.counter, self.short_ledger.protection),
                   'declared companion prestate precedes driving, not an actual-selected expectation')
        if preserve:
            self.check(sum(edge[1] == 'penalty' for edge in EDGES[self.mode]), len(self.available_errors),
                       'all original long errors precede the short consumer')
        accepted = super().open_original()
        self.short_window = 'preserve' if preserve else 'release'
        self.acceptance_identity = self.short_identity
        return accepted

    def accepted_provider(self, value, tick):
        if self.short_window is None:
            super().accepted_provider(value, tick)
            if (self.mode == 'direction-crossing' and 'NT-error-restores-T' in self.confirmed
                    and 'T-correction-restores-protection' not in self.confirmed):
                self.check((4, 0), (value.counter, self.observed_protection[1][value.index]),
                           'fresh restored T direction still has zero actual protection')
                self.check(True, tick > self.confirmed['NT-error-restores-T'][2],
                           'restored T consumer follows the actual NT error confirmation')
                self.restored_taken = self.first, tick
                self.reach('restored-T-before-protection', tick, identity=asdict(self.identity),
                           owner=self.first.sequence, prediction_tick=tick, counter=4, protection=0)
            return
        expected = (6, 0) if self.short_window == 'preserve' else (7, 1)
        self.check(expected, (value.counter, self.observed_protection[0][value.index]),
                   'exact companion consumer proves its independent direction and actual protection')
        self.short_selected = self.first, tick, self.short_window

    def window_receipt(self, source):
        if self.short_window is None:
            return super().window_receipt(source)
        token = self.remember(source)
        self.check(True, token.sequence == self.selected.sequence and token.history is self.selected.history
                   and source.prediction_tick == self.selected_tick and self.acceptance.done(),
                   'companion S3 receipt belongs to its exact monitor-closed S1 window')
        self.short_receipts[self.short_window] = source
        if self.short_window == 'preserve':
            self.check(True, source.prediction_tick > self.available_errors[-1]['actual_confirmation_tick'],
                       'companion consumer follows every actual long error confirmation')
            value = provider(self.pipeline.model.sources, token)
            self.check((self.short_identity.key, self.short_identity.tag, self.short_identity.position, 6),
                       (value.key, value.tag, value.position, value.counter),
                       'unused short resident retains its original identity and direction')
            self.short_consumer = dict(identity=asdict(self.short_identity), owner=token.sequence,
                prediction_tick=source.prediction_tick, receipt_tick=source.meta_tick,
                counter=6, protection=0, last_long_confirmation=self.available_errors[-1]['actual_confirmation_tick'])
            self.reach('short-resident-preserved', source.meta_tick, **self.short_consumer)
        self.window_active = False

    def rule_names(self):
        return rules(self.mode)

    @property
    def requires_parallel_allocation(self):
        return False

    def seed_candidates(self):
        identity = intended_identity(self.pc)
        return [row for row in super().seed_candidates()
                if row[0] == identity.key and (row[2].tag, row[2].position) == (identity.tag, identity.position)]

    def candidates(self, row, events, cycle, model, phase, previous):
        result = super().candidates(row, events, cycle, model, phase, previous)
        control = row['observed']['early_direction']['maintenance']
        self.actual_failures = control['low']
        self.failure_decision = None if self.processing_allocation is None else self.processing_allocation[1]
        self.processing_before = self.processing_allocation
        self.check(self.failure_ledger.count, self.actual_failures,
                   'reset-derived failures count every qualified opportunity, including preparation')
        self.check(int(self.failure_decision is not None), control['fire'], 'actual registered learning opportunity')
        self.original_error = False
        if self.identity is not None and self.applied is not None:
            decision = guidance(self.applied.feedback, self.identity)
            self.original_error = decision is not None and decision[1] == 'penalty'
            if self.original_error:
                self.check((1, None, True),
                    (self.failure_decision.provider, self.failure_decision.candidate, self.failure_decision.failed),
                    'longest original error cannot allocate backward into a short record')
                if self.mode in FREE_SHORT_MODES:
                    self.check(True, self.short_release is not None, 'companion protection was actually released first')
                    feedback, _, protection = self.processing_allocation
                    self.check((self.short_identity.index, 0), (feedback.indices[0], protection[0]),
                               'same learning READ has a genuinely available shorter candidate')
        return result

    def checked(self, tick, *candidates):
        previous = self.failure_pending
        before = self.failure_ledger.count
        super().checked(tick, *candidates)
        if previous is not None:
            written, event, old, expected = previous
            self.check(written+2, tick, 'failure accounting must cross the next actual comparison')
            self.check(expected, self.actual_failures, 'one real failed opportunity increments once')
            self.confirmed_failures.append((event.owner, written, tick, old, expected))
            self.reach('last-provider-error-accounted', tick, identity=asdict(self.identity),
                       owner=event.owner, failure_before=old, failure_after=expected,
                       written_tick=written, actual_confirmation_tick=tick, allocation_mask=0)
            if self.mode in FREE_SHORT_MODES:
                witness = dict(self.available_pending, actual_confirmation_tick=tick)
                self.available_errors.append(witness)
                self.reach('no-backward-allocation-with-free-short', tick, **witness)
        self.available_pending = None
        self.failure_pending = None
        self.failure_ledger.apply(self.failure_decision)
        self.check(self.failure_ledger.count, self.pipeline.model.sources.short.low_tick,
                   'cycle reference and independent failed-opportunity ledger agree')
        if self.original_error:
            self.check(before+1, self.failure_ledger.count, 'exactly one failure from this original S3 guidance')
            self.check(True, self.pending is not None, 'same owner owns protection loss and failed allocation')
            event = self.pending[1]
            self.failure_pending = tick, event, before, self.failure_ledger.count
            if self.mode in FREE_SHORT_MODES:
                feedback, _, protection = self.processing_before
                self.available_pending = dict(owner=event.owner, identity=asdict(self.identity),
                    short_identity=asdict(self.short_identity), learning_indices=feedback.indices,
                    common_read_protection=protection, written_tick=tick, allocation_mask=0)
        if self.short_ledger is not None:
            self.check_short(tick)

    def check_short(self, tick):
        if self.short_pending is not None:
            written, event = self.short_pending
            self.check((written+2, event.after),
                       (tick, self.observed_protection[0][self.short_identity.index]),
                       'short release crosses the next complete actual comparison')
            self.check((7, 6, 1, 0),
                       (event.counter_before, event.counter_after, event.before, event.after),
                       'companion loses protection through its own original error')
            self.check((7, 2), (self.ledger.counter, self.ledger.protection),
                       'companion release leaves the original long record unchanged')
            self.short_release = dict(identity=asdict(self.short_identity), **asdict(event),
                written_tick=written, actual_confirmation_tick=tick, compared_protection_cells=1024)
            self.reach('short-available-before-long-error', tick, **self.short_release)
        self.short_pending = None
        if self.applied is not None and (decision := guidance(self.applied.feedback, self.short_identity)) is not None:
            owner = next(owner for feedback, owner in self.offers if feedback is self.applied.feedback)
            event = self.short_ledger.apply(owner.sequence, *decision)
            if (self.short_selected is not None and owner.sequence == self.short_selected[0].sequence
                    and owner.history is self.short_selected[0].history and self.short_selected[2] == 'release'):
                self.short_pending = tick, event
        sources = self.pipeline.model.sources; entry = resident(sources, self.short_identity.key)
        self.check((True, self.short_identity.tag, self.short_identity.position, self.short_ledger.counter,
                    self.short_ledger.protection),
                   (entry.valid, entry.tag, entry.position, entry.counter,
                    sources.short.useful[0].get(self.short_identity.index, 0)),
                   'all original long learning preserves the independently owned short resident')

    def finish_boundaries(self, owners):
        if self.mode == 'direction-crossing':
            expected = [('penalty',7,6,2,1), ('penalty',6,5,1,0), ('penalty',5,4,0,0),
                        ('penalty',4,3,0,0), ('penalty',3,4,0,0), ('reward',4,5,0,1)]
            self.check(expected, [(e.kind,e.counter_before,e.counter_after,e.before,e.after)
                for e,_,_ in (self.confirmed[name] for name,*_ in EDGES[self.mode] if name in self.confirmed)],
                'long T error, NT error and T correction preserve their distinct direction/protection meanings')
            self.check(True, self.restored_taken is not None, 'fresh zero-protection T consumer is mandatory')
            token, prediction = self.restored_taken
            reward, written, actual = self.confirmed['T-correction-restores-protection']
            published = self.pipeline.model.published.get(token.sequence)
            self.check(True, published is not None and published.history is token.history,
                       'restored consumer retains its original published checkpoint')
            self.check(True, token.sequence == reward.owner
                       and self.confirmed['NT-error-restores-T'][2] < prediction < written < actual,
                       'same fresh restored T source owns the later protection reward')
        if self.mode in FREE_SHORT_MODES:
            self.check(True, self.short_release is not None and self.short_consumer is not None,
                       'available companion and its later preserved consumer are both mandatory')
            expected = [dict(owner=event.owner, identity=asdict(self.identity),
                short_identity=asdict(self.short_identity),
                learning_indices=(self.short_identity.index, self.identity.index),
                common_read_protection=(0, event.before), written_tick=written,
                actual_confirmation_tick=actual, allocation_mask=0)
                for event, written, actual in (self.confirmed[name] for name, kind, *_ in EDGES[self.mode]
                                               if kind == 'penalty' and name in self.confirmed)]
            self.check(expected, self.available_errors,
                       'every original long failure has its exact free-short READ and actual confirmation')
            release, consumer = self.short_receipts.get('release'), self.short_receipts.get('preserve')
            self.check(True, release is not None and consumer is not None, 'both companion receipts must remain owned')
            release_owner = self.pipeline.source_token(release).sequence
            self.check((asdict(self.short_identity), release_owner, 'penalty', 7, 6, 1, 0, 1024),
                tuple(self.short_release[key] for key in ('identity','owner','kind','counter_before',
                    'counter_after','before','after','compared_protection_cells')),
                'free-short prerequisite retains its own original source and confirmed state')
            self.check(True, release.prediction_tick < self.short_release['written_tick']
                and self.short_release['written_tick']+2 == self.short_release['actual_confirmation_tick']
                < self.available_errors[0]['written_tick'], 'short availability is actual before the first long error')
            self.check(dict(identity=asdict(self.short_identity), owner=self.pipeline.source_token(consumer).sequence,
                prediction_tick=consumer.prediction_tick, receipt_tick=consumer.meta_tick, counter=6, protection=0,
                last_long_confirmation=self.available_errors[-1]['actual_confirmation_tick']), self.short_consumer,
                'companion consumer witness cannot be substituted by a long or earlier source')
        if self.short_seed is not None:
            self.check(self.short_seed.snapshot, self.pipeline.model.sources.short_snapshot(self.short_seed.owner),
                       'companion initial allocation snapshot remains immutable')
        self.check(None, self.short_pending, 'companion learning is actually confirmed')
        self.check(None, self.failure_pending, 'all original failed opportunities actually confirmed')
        self.check(sum(edge[1] == 'penalty' for edge in EDGES[self.mode]), len(self.confirmed_failures),
                   'each declared original error owns one independently confirmed failure')
        original_errors = [self.confirmed[name] for name, kind, *_ in EDGES[self.mode]
                           if kind == 'penalty' and name in self.confirmed]
        self.check([(event.owner, written, actual) for event, written, actual in original_errors],
                   [(owner, written, actual) for owner, written, actual, _, _ in self.confirmed_failures],
                   'failed opportunities align with the same original owners and actual protection confirmations')
        super().finish_boundaries(owners)

    def closure_witness(self, rule):
        if rule == 'restored-T-before-protection':
            token, prediction = self.restored_taken
            return dict(identity=asdict(self.identity), owner=token.sequence, prediction_tick=prediction,
                        counter=4, protection=0,
                        previous_error_confirmation=self.confirmed['NT-error-restores-T'][2],
                        subsequent_reward_owner=self.confirmed['T-correction-restores-protection'][0].owner)
        if rule == 'short-available-before-long-error':
            return self.short_release
        if rule == 'short-resident-preserved':
            return self.short_consumer
        if rule == 'no-backward-allocation-with-free-short':
            return dict(events=self.available_errors, short_release=self.short_release,
                        short_consumer=self.short_consumer)
        failures = [dict(owner=owner, written_tick=written, actual_confirmation_tick=actual,
                         failure_before=before, failure_after=after, allocation_mask=0)
                    for owner, written, actual, before, after in self.confirmed_failures]
        if rule == 'last-provider-error-accounted':
            return dict(confirmed_failures=failures, all_failures_from_reset=self.failure_ledger.failures,
                        global_failure_counter_final=self.failure_ledger.count)
        if rule in self.confirmed and self.confirmed[rule][0].kind == 'penalty':
            owner = self.confirmed[rule][0].owner
            return {key: value for key, value in next(row for row in failures if row['owner'] == owner).items()
                    if key not in ('owner', 'written_tick', 'actual_confirmation_tick')}
        return super().closure_witness(rule)
