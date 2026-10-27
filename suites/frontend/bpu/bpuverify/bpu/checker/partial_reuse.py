"""Compare partial service, clean-space reuse and all preserved identities."""
from copy import deepcopy
from toffee import XEvent, XPhase
from bpuverify.bpu.checker.neighbor_migration import NeighborMigrationChecks
from bpuverify.bpu.coverage.partial_reuse import RULES
from bpuverify.bpu.model.tage.partial_reuse import (
    HISTORY_PATHS, NEIGHBOR_NAMES, INPUT_NAMES, INITIAL_INPUTS, preparation, expected_profile, mixed_profile)
from bpuverify.bpu.model.tage.dual_migration import OUTCOMES, TABLE
from bpuverify.bpu.model.tage.service import pending_plan, learning_inflight


class PartialReuseChecks(NeighborMigrationChecks):
    history_paths = HISTORY_PATHS
    neighbor_names = NEIGHBOR_NAMES
    input_names = INPUT_NAMES
    rules = RULES
    neighbor_steps = staticmethod(preparation)
    history_profile = staticmethod(expected_profile)

    def __init__(self, pipeline, coverage):
        super().__init__(pipeline, coverage)
        self.partial_receipt, self.partial_prepared, self.partial_candidate = None, None, None
        self.partial_event, self.partial_end_tick = None, None
        self.full_hits = []

    def arm_neighbor(self, current):
        super().arm_neighbor(current)
        # Preparation's four independent neighbors are reordered into two
        # semantic bursts, with one real service pair between the bursts.
        self.requests = (*self.requests[:3], self.requests[4], self.requests[3], *self.requests[5:])
        self.expected_offers = (*self.expected_offers[:3], self.expected_offers[4],
                                self.expected_offers[3], *self.expected_offers[5:])
        self.input_frozen = tuple(deepcopy(s.meta.resolve) for s in self.requests)
        self.input_defined = tuple(deepcopy(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s)))
                                   for s in self.requests)
        fresh = self.expected_offers[3]
        self.initial_plan = tuple(tuple(self.side_payloads[n][o] for n in NEIGHBOR_NAMES[:3]) + (fresh[o],)
                                  for o in range(2))
        order = (NEIGHBOR_NAMES[3], *NEIGHBOR_NAMES[1:3])
        self.final_plan = tuple(tuple(self.side_payloads[n][o] for n in order) + (self.target_payload[o],)
                                for o in range(2))
        self.complete_plan = tuple((self.side_payloads[NEIGHBOR_NAMES[0]][o], *self.final_plan[o]) for o in range(2))

    def begin_read_window(self):
        self.check('neighbor-armed', self.phase, 'partial reuse starts once after normal preparation')
        self.phase = 'initial-holding'

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            self.last = event.tick, deepcopy(row)
            self.check(False, bool(row['reset']), 'reset cannot impersonate service or release capacity')
            self.check(0, row['reads'][1]['valid'], 'each feedback owns a genuine nonreread source')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'actual predictions block both services')
            holding = self.phase in ('initial-holding', 'refill-holding')
            if holding:
                self.check(True, bool(busy), 'read competition continues throughout each held phase')
            if row['training']['valid'] and row['training']['ready']:
                self.check(True, holding, 'only the two declared original-source bursts may accept')
                limit = INITIAL_INPUTS if self.phase == 'initial-holding' else self.input_count
                self.check(True, len(self.input_ticks) < limit, 'no extra accepted source in this phase')
                p = row['prediction']
                self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank),
                           'a genuine prediction accepts beside every feedback')
                self.input_ticks.append(event.tick)
            flags = tuple(p['valid'] for p in row['incoming'])
            self.check(True, flags in ((0, 0), (1, 1)), 'both complete branch proposals arrive together')
            if any(flags):
                self.check(True, holding, 'proposals belong to a declared held phase')
                index = len(self.offered)
                limit = INITIAL_INPUTS if self.phase == 'initial-holding' else self.input_count
                self.check(True, index < limit and index < len(self.input_ticks), 'one complete proposal per actual source')
                bits = tuple(p['bits'] for p in row['incoming'])
                self.check(self.expected_offers[index], bits, 'each input retains its own complete original proposal')
                self.check(True, len(row['dirty']) == 2 and all(len(v) == 4 for v in row['dirty']), 'full actual retention prestate')
                wanted = index if index < INITIAL_INPUTS else 3 if index == INITIAL_INPUTS else 4
                self.check((wanted,) * 2, tuple(sum(v) for v in row['dirty']), 'partial service frees one result before new identity reuse')
                if index >= INITIAL_INPUTS:
                    self.check((1, 1), tuple(map(len, self.written.values())), 'exactly one compared service per owner before reuse')
                    self.check(True, event.tick > self.partial_end_tick, 'reused input follows actual service window closure')
                    if index > INITIAL_INPUTS:
                        self.check(((1, 1, 1, 1),) * 2, tuple(tuple(v) for v in row['dirty']), 'each stale migrated hit has actual full preconditions')
                        self.full_hits.append(dict(index=index, tick=event.tick, dirty=deepcopy(row['dirty']), bits=deepcopy(bits)))
                self.check(True, event.tick > self.input_ticks[index], 'proposal follows its own actual input')
                if index and index != INITIAL_INPUTS:
                    self.check(self.offered[-1]['tick'] + 2, event.tick, 'each burst has adjacent complete proposals')
                self.offered.append(dict(tick=event.tick, bits=deepcopy(bits), dirty=deepcopy(row['dirty'])))
            if holding and self.pending_ready:
                self.check(((1, 0), (1, 0)), tuple((p['valid'], p['ready']) for p in row['writes']), 'all remaining service fronts stay blocked')
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        initial = self.phase == 'initial-holding'
        self.check(True, initial or self.phase == 'refill-holding', 'only declared held bursts qualify')
        start, count = (0, INITIAL_INPUTS) if initial else (INITIAL_INPUTS, self.input_count - INITIAL_INPUTS)
        self.check(start, len(self.accepted), 'each source burst qualifies once in order')
        self.check(count, len(events), 'all original sources in this burst must actually accept')
        for offset, (source, event) in enumerate(zip(self.requests[start:start + count], events, strict=True)):
            self.outcome(event, source, OUTCOMES)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'each original source qualifies without a reread')
            if offset:
                self.check(events[offset - 1][0] + 2, event[0], 'feedbacks overlap on adjacent cycles within each burst')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks[start:]), 'all public receipts belong to the declared burst')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])), 'Main and TAGE enabled at every acceptance')
        self.accepted.extend(events)

    def pending(self):
        initial = self.phase == 'initial-holding'
        self.check(True, initial or self.phase == 'refill-holding', 'qualify one complete held phase')
        count = INITIAL_INPUTS if initial else self.input_count
        self.check(count, len(self.accepted), 'all original acceptances mandatory before pending comparison')
        self.check(count, len(self.offered), 'all complete proposals mandatory before pending comparison')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'learning matured separately from actual service')
        self.check(self.initial_plan if initial else self.final_plan, pending_plan(tage, TABLE, self.bank),
                   'new identity uses its own result while every remaining logical result survives')
        self.check(self.initial_overflows, tage.cache[TABLE, self.bank].overflows, 'no pending result was evicted')
        self.check((0, 0) if initial else (1, 1), tuple(map(len, self.written.values())), 'only the declared partial pair has serviced')
        self.check(((1, 1, 1, 1),) * 2, tuple(tuple(v) for v in self.last[1]['dirty']), 'both current owners actually full after learning')
        self.pending_ready = True
        if initial:
            self.reach(self.rules[2], sources=self.input_names[:INITIAL_INPUTS], actual_proposals=deepcopy(self.offered),
                       expected_pending=self.initial_plan, actual_commits=0)
        else:
            self.check((5, 6), tuple(v['index'] for v in self.full_hits), 'both old sources own a full-capacity migrated hit')
            self.check(tuple(self.offered[i]['tick'] for i in (5, 6)), tuple(v['tick'] for v in self.full_hits), 'full witnesses match actual old proposals')
            self.reach(self.rules[4], new_identity_proposal=deepcopy(self.offered[4]), expected_pending=self.final_plan,
                       partial_writes=deepcopy(self.written), no_overflow=True)
            self.reach(self.rules[5], actual_full_hits=deepcopy(self.full_hits), expected_target=self.target_payload)

    def begin_partial(self, receipt, prepared):
        self.check('initial-holding', self.phase, 'partial service begins after the first held burst')
        self.check(True, self.pending_ready, 'full pending results compared before partial service')
        self.check((0, 0), tuple(map(len, self.written.values())), 'partial service opens before any write')
        self.check(False, receipt.done(), 'service completion receipt is fresh')
        self.check(False, prepared.done(), 'pre-edge scheduling receipt is fresh')
        self.partial_receipt, self.partial_prepared = receipt, prepared
        self.release_tick, self.phase = self.pipeline.last_tick, 'partial-service'

    def prepare_partial(self, event, row):
        self.raise_failure()
        if self.phase != 'partial-service' or not all(p['valid'] and p['ready'] for p in row['writes']):
            return
        self.check(True, isinstance(event, XEvent) and event.phase is XPhase.DRIVE_STABLE,
                   'schedule public rise-write control at the real pre-edge preparation phase')
        self.check(False, self.partial_prepared.done(), 'no second service candidate before read restoration')
        self.check((0, 0), tuple(map(len, self.written.values())), 'a service candidate is not an actual service')
        self.check(False, any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads']),
                   'service preparation has no competing prediction read')
        self.check(True, event.tick > self.release_tick, 'candidate follows the declared window opening')
        self.check(tuple(p[0] for p in self.complete_plan), tuple(p['bits'] for p in row['writes']),
                   'only the two complete first-neighbor payloads may prepare')
        self.check(((1, 1, 1, 1),) * 2, tuple(tuple(v) for v in row['dirty']), 'candidate sees full pending capacity')
        self.partial_candidate = dict(tick=event.tick, writes=deepcopy(row['writes']), dirty=deepcopy(row['dirty']))
        self.partial_prepared.set_result(event)

    def partial_complete(self, event):
        self.check('partial-service', self.phase, 'one actual partial window closes once')
        self.check((1, 1), tuple(map(len, self.written.values())), 'one full compared result per owner, not a full drain')
        self.check(True, self.partial_receipt.done(), 'driver closure has an actual compared pair')
        self.check(True, self.partial_prepared.done() and self.partial_candidate is not None, 'actual pair has its pre-edge scheduling witness')
        self.check(self.partial_receipt.result(), event, 'driver closed on the same real service event')
        self.check(self.partial_candidate['tick'] + 1, event.tick, 'prepared pair actually accepted at the next rising boundary')
        self.check((event.tick, event.tick), tuple(v[0][0] for v in self.written.values()), 'both current owners serviced together')
        self.check(tuple(p[1:] for p in self.initial_plan),
                   pending_plan(self.pipeline.model.sources.tage, TABLE, self.bank), 'three unserviced results survive window closure')
        self.check((3, 3), tuple(sum(v) for v in self.last[1]['dirty']), 'actual partial service leaves three obligations per owner')
        self.check(True, any(p['valid'] and p['mask'] & (1 << self.bank) for p in self.last[1]['reads']), 'actual prediction reads restored before reuse')
        self.partial_event, self.partial_end_tick = event, self.pipeline.last_tick
        self.phase, self.pending_ready = 'refill-holding', False
        self.reach(self.rules[3], actual_writes=deepcopy(self.written), accepted_tick=event.tick,
                   preparation=deepcopy(self.partial_candidate), resumed_tick=self.partial_end_tick, remaining_per_owner=3)

    def write_accepted(self, owner, transfer):
        partial = self.phase == 'partial-service'
        self.check(True, partial or self.phase == 'service', 'service only in the two declared windows')
        self.check(True, owner in (0, 1), 'service has a declared current owner')
        index = len(self.written[owner])
        self.check(True, index < (1 if partial else 5), 'partial pair cannot silently drain another result')
        self.check(True, transfer.accepted_tick > max(self.release_tick, self.offered[-1]['tick']), 'actual service follows window opening and all required proposals')
        if partial:
            self.check(True, self.partial_candidate is not None, 'prepared control closure precedes actual service')
            self.check(self.partial_candidate['tick'] + 1, transfer.accepted_tick, 'SDK confirms the exact prepared edge')
        self.check(self.complete_plan[owner][index], transfer.value, 'full SDK result owns the correct logical identity and counter')
        self.check(True, isinstance(transfer.event, XEvent) and transfer.event.phase is XPhase.RISING_STABLE
                   and transfer.event.tick == transfer.accepted_tick, 'service is confirmed at its actual SDK acceptance boundary')
        if index > 1:
            self.check(self.written[owner][-1][0] + 2, transfer.accepted_tick, 'final four results service on adjacent boundaries')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))
        if partial and tuple(map(len, self.written.values())) == (1, 1):
            self.check(self.written[0][0][0], self.written[1][0][0], 'both partial services share one boundary')
            self.partial_receipt.set_result(transfer.event)

    def consume(self, phase, name, source):
        self.check(True, phase in ('blocked', 'serviced') and name in self.history_paths, 'declared history and visibility phase')
        self.check(True, (phase, name) not in self.consumers, 'each required consumer compares once')
        blocked = phase == 'blocked'
        self.check('refill-holding' if blocked else 'consuming', self.phase, 'consumer follows its actual service boundary')
        self.check(True, self.pending_ready, 'all pending effects qualified before consumers')
        self.check((1, 1) if blocked else (5, 5), tuple(map(len, self.written.values())), 'consumer sees exactly the declared service count')
        after = self.accepted[-1][0] if blocked else max(v[-1][0] for v in self.written.values())
        self.check(True, source.prediction_tick > after, 'a fresh query follows the required learning or service')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'fresh consumer keeps the exact owned history')
        self.check(mixed_profile(name) if blocked else expected_profile(name, serviced=True), self.profile(source),
                   'complete Main/TAGE identity and mixed old/new visibility')
        self.consumers[phase, name] = source
        if all((phase, n) in self.consumers for n in self.history_paths):
            witness = {n: dict(prediction_tick=self.consumers[phase, n].prediction_tick,
                meta_tick=self.consumers[phase, n].meta_tick, compared=self.profile(self.consumers[phase, n])) for n in self.history_paths}
            self.reach(self.rules[6 if blocked else 8], consumers=witness)

    def release(self):
        self.check('refill-holding', self.phase, 'final release follows complete reuse')
        self.check(True, all(('blocked', n) in self.consumers for n in self.history_paths), 'all six mixed-visibility consumers precede final service')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def services_complete(self):
        self.check('service', self.phase, 'qualify all ten actual services once')
        self.check((5, 5), tuple(map(len, self.written.values())), 'all original and reused identities actually serviced')
        self.check(tuple(t for t, _ in self.written[0]), tuple(t for t, _ in self.written[1]), 'current owners share each service boundary')
        self.reach(self.rules[7], actual_writes=deepcopy(self.written), partial_commits=2, final_commits=8)
        self.phase = 'consuming'

    def finish(self):
        self.check(False, self.closed, 'checked credit is single-use')
        self.check('consuming', self.phase, 'all real services precede final qualification')
        self.check({(p, n) for p in ('blocked', 'serviced') for n in self.history_paths}, set(self.consumers), 'all twelve fresh consumers mandatory')
        self.check(self.input_frozen, tuple(s.meta.resolve for s in self.requests), 'all seven actual input snapshots immutable')
        self.check(self.input_defined, tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                   for s in self.requests), 'all seven independently owned snapshots immutable')
        self.reach(self.rules[9], input_meta_ticks=[s.meta_tick for s in self.requests], compared_consumers=12)
        self.check(set(self.rules), self.completed, 'every semantic obligation complete before checked')
        self.closed = True
        for rule in self.rules:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        for s in (*self.sources, *self.migration_before.values(), *self.before.values(), *self.consumers.values()):
            self.pipeline.retire_source(s.meta_tick)
