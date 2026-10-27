"""Partial service is per logical result, never an atomic history commit."""
from copy import deepcopy

from toffee import XEvent, XPhase

from bpuverify.bpu.checker.asymmetric_retirement import AsymmetricRetirementChecks
from bpuverify.bpu.coverage.mixed_visibility import RULES
from bpuverify.bpu.model.tage.asymmetric_retirement import PRELUDE_PLAN
from bpuverify.bpu.model.tage.dual_migration import TABLE
from bpuverify.bpu.model.tage.mixed_visibility import PROGRAMS, PARTIAL_PLAN, FIRST_SERVICE, DESTINATIONS
from bpuverify.bpu.model.tage.service import learning_inflight, pending_plan


class MixedVisibilityChecks(AsymmetricRetirementChecks):
    rules = RULES
    programs = PROGRAMS

    def __init__(self, pipeline, coverage, program):
        if program not in self.programs:
            raise ValueError('unknown mixed-visibility program')
        super().__init__(pipeline, coverage)
        self.program = program
        self.saved, self.snapshots, self.definitions = {}, {}, {}
        self.partial_receipt = self.partial_prepared = self.partial_candidate = None
        self.partial_end_tick, self.refill_qualified = None, False

    @property
    def input_count(self):
        return len(self.requests)

    def remember(self, source):
        identity = id(source)
        if identity in self.snapshots:
            self.check(self.snapshots[identity], source.meta, 'a saved input cannot change before reuse')
            return
        self.snapshots[identity] = deepcopy(source.meta)
        self.definitions[identity] = deepcopy(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(source)))

    def arm_asymmetric(self, warm_source, warm_event, current):
        super().arm_asymmetric(warm_source, warm_event, current)
        for source in self.requests:
            self.remember(source)
        self.saved['old-target'] = self.sources[1]

    def save_old_neighbor(self, source):
        self.check('neighbor-armed', self.phase, 'old neighbor captured before any held input')
        self.check(False, 'old-neighbor' in self.saved, 'old neighbor checkpoint captured once')
        self.check(self.program.profile('initial', 'neighbor'), self.profile(source), 'old neighbor has genuine 2/5 qualification')
        self.check(self.read(self.before['neighbor']).context, self.read(source).context, 'old neighbor belongs to its own history')
        self.check(True, all(self.pipeline.source_token(source).history is not self.pipeline.source_token(s).history
                            for s in self.requests), 'old neighbor is not the already submitted checkpoint')
        self.saved['old-neighbor'] = source
        self.remember(source)

    @staticmethod
    def dirty_for(plan):
        dirty = [[0] * 4 for _ in range(2)]
        for owner, versions in enumerate(plan):
            for name, _ in versions:
                expected_owner, rank = DESTINATIONS[name]
                if owner != expected_owner:
                    raise ValueError('logical result changed its declared current owner')
                dirty[owner][rank] = 1
        return tuple(tuple(v) for v in dirty)

    def begin_partial(self, receipt, prepared):
        self.check('holding', self.phase, 'one partial boundary follows the initial held window')
        self.check(True, self.pending_ready and self.pending_round == 1, 'complete initial learning qualified')
        self.check(True, all(('initial', n) in self.consumers for n in self.history_paths), 'all old storage consumers precede partial service')
        self.check((0, 0), tuple(map(len, self.written.values())), 'partial boundary begins before any service')
        self.check((False, False), (receipt.done(), prepared.done()), 'fresh prepared and accepted receipts')
        self.partial_receipt, self.partial_prepared = receipt, prepared
        self.release_tick, self.phase = self.pipeline.last_tick, 'partial-service'

    def prepare_partial(self, event, packet):
        self.raise_failure()
        row = packet['state']
        if self.phase != 'partial-service' or not all(p['valid'] and p['ready'] for p in row['writes']):
            return
        self.check(True, isinstance(event, XEvent) and event.phase is XPhase.DRIVE_STABLE,
                   'public rise-write stop is prepared at the pre-edge SDK phase')
        self.check(False, self.partial_prepared.done(), 'one prepared boundary only')
        self.check((0, 0), tuple(map(len, self.written.values())), 'preparation is not accepted service')
        self.check(False, any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads']),
                   'prepared services have no competing read')
        self.check(True, event.tick > self.release_tick, 'preparation follows service-window opening')
        self.check(tuple(self.payload(p) for p in FIRST_SERVICE), tuple(p['bits'] for p in row['writes']),
                   'first results belong to different histories, not a paired source')
        self.check(self.dirty_for(PRELUDE_PLAN), tuple(tuple(v) for v in row['dirty']), 'all four initial results still pending')
        self.partial_candidate = dict(tick=event.tick, writes=deepcopy(row['writes']), dirty=deepcopy(row['dirty']))
        self.partial_prepared.set_result(event)

    def partial_complete(self, event):
        self.check('partial-service', self.phase, 'one actual partial boundary closes once')
        self.check((1, 1), tuple(map(len, self.written.values())), 'only one complete result per owner serviced')
        self.check(True, self.partial_receipt.done() and self.partial_prepared.done(), 'preparation and actual acceptance are both mandatory')
        self.check(self.partial_receipt.result(), event, 'driver closes on the compared SDK acceptance')
        self.check(self.partial_candidate['tick'] + 1, event.tick, 'prepared pair accepts on the next rising boundary')
        self.check((event.tick, event.tick), tuple(v[0][0] for v in self.written.values()), 'exact one-boundary partial release')
        self.check(self.concrete(PARTIAL_PLAN), pending_plan(self.pipeline.model.sources.tage, TABLE, self.bank),
                   'both B results remain pending although two A results serviced')
        self.check(self.dirty_for(PARTIAL_PLAN), tuple(tuple(v) for v in self.last[1]['dirty']), 'actual remaining B obligations')
        self.check(True, any(p['valid'] and p['mask'] & (1 << self.bank) for p in self.last[1]['reads']),
                   'actual same-bank read competition restored')
        self.partial_end_tick, self.phase, self.pending_ready = self.pipeline.last_tick, 'mixed-holding', False
        self.reach(self.rules[9], actual_writes=deepcopy(self.written), preparation=deepcopy(self.partial_candidate),
                   accepted_tick=event.tick, resumed_tick=self.partial_end_tick, expected_remaining=self.concrete(PARTIAL_PLAN))

    def arm_mixed(self):
        self.check('mixed-holding', self.phase, 'mixed-source feedback armed once after partial service')
        self.check(True, all(('mixed', n) in self.consumers for n in self.history_paths), 'every genuine mixed consumer must precede new learning')
        self.saved.update({'mixed-target': self.consumers['mixed', 'original'],
                           'mixed-neighbor': self.consumers['mixed', 'neighbor']})
        for source in self.saved.values():
            self.remember(source)
        self.requests = (*self.requests[:3], *(self.saved[n] for n in self.program.late_sources))
        tokens = tuple(self.pipeline.source_token(s) for s in self.requests)
        self.check(self.input_count, len({id(t.history) for t in tokens}), 'every actually submitted checkpoint distinct')
        self.input_frozen = tuple(self.snapshots[id(s)] for s in self.requests)
        self.input_defined = tuple(self.definitions[id(s)] for s in self.requests)
        self.expected_offers = (*self.expected_offers[:3], *(tuple(None if p is None else self.payload(p) for p in pair)
            for pair in self.program.late_proposals))
        self.expected_plan = self.concrete(self.program.final_plan)
        self.phase = 'refill-holding'

    def late_input_cadence(self,previous,current):
        self.check(previous+2,current,'old histories truly accepted on adjacent cycles')

    def late_proposal_cadence(self,index,tick):
        self.check(self.offered[-1]['tick']+2,tick,'different old histories learn on adjacent cycles')

    def capture_state(self, event, packet):
        if self.phase in ('neighbor-armed', 'holding', 'partial-service'):
            return super().capture_state(event, packet)
        if self.failure is not None:
            return
        try:
            row = packet['state']
            self.last = event.tick, row
            self.check(0, row['reset'], 'reset cannot replace a declared lifecycle')
            self.check(0, row['reads'][1]['valid'], 'mixed and old feedback independently qualify without reread')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'real reads block both services')
            if self.phase in ('mixed-holding', 'refill-holding'):
                self.check(True, bool(busy), 'mixed consumers and new learning keep uninterrupted same-bank reads')
            if row['training']['valid'] and row['training']['ready']:
                self.check('refill-holding', self.phase, 'only declared late inputs may accept')
                self.check(True, len(self.input_ticks) < self.input_count, 'no extra late feedback')
                p = row['prediction']
                self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank), 'prediction accepts beside late feedback')
                self.input_ticks.append(event.tick)
            if any(p['valid'] for p in row['incoming']):
                self.check('refill-holding', self.phase, 'complete late proposal belongs to this held window')
                index = len(self.offered)
                self.check(True, 3 <= index < self.input_count and index < len(self.input_ticks), 'one proposal per actual late source')
                actual = tuple(p['bits'] if p['valid'] else None for p in row['incoming'])
                self.check(self.expected_offers[index], actual, 'old or mixed source keeps its own proposal qualification')
                self.check(self.dirty_for(self.program.pending_before(index - 3)), tuple(tuple(v) for v in row['dirty']),
                           'actual serviced and pending versions have independent lifetimes')
                hits, ranks = [], []
                for port, logical in enumerate(self.program.late_proposals[index - 3]):
                    if logical is None:
                        hits.append(None); ranks.append(None)
                        continue
                    owner, rank = DESTINATIONS[logical[0]]
                    observed = packet['owner_hits'][port]
                    hit = int(any(observed['owner0'])), observed['owner1']
                    self.check((int(owner == 0), int(owner == 1)), hit, 'actual full key reaches its own current owner')
                    self.check(rank, packet['hit_ranks'][port][owner], 'actual hit preserves the independently derived lifetime')
                    hits.append(hit); ranks.append(rank)
                self.check(True, event.tick > self.input_ticks[index] and event.tick > self.partial_end_tick,
                           'late proposal follows its own input and partial boundary')
                if index > 3:
                    self.late_proposal_cadence(index,event.tick)
                self.offered.append(dict(tick=event.tick, bits=deepcopy(actual), dirty=deepcopy(row['dirty']),
                                         hits=tuple(hits), ranks=tuple(ranks)))
            if self.phase == 'refill-holding' and self.pending_ready:
                self.check(((1, 0), (1, 0)), tuple((p['valid'], p['ready']) for p in row['writes']), 'both remaining owner fronts blocked')
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        if self.phase == 'holding':
            return super().accepted_burst(events)
        self.check('refill-holding', self.phase, 'late feedback after genuine mixed consumers')
        self.check(3, len(self.accepted), 'late burst qualifies once after the prelude')
        self.check(len(self.program.late_sources), len(events), 'all declared late inputs accepted')
        for index, (source, event, outcomes) in enumerate(zip(self.requests[3:], events, self.program.late_outcomes, strict=True)):
            self.outcome(event, source, outcomes)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'each source has nonreread qualification')
            if index:
                self.late_input_cadence(events[index-1][0],event[0])
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks[3:]), 'driver receipts equal actual public late acceptances')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])), 'both predictors enabled at actual acceptance')
        self.accepted.extend(events)
        self.reach(self.rules[2], late_sources=self.program.late_sources, accepted_ticks=list(self.input_ticks),
                   prediction_concurrent=True, reread=False)

    def pending(self):
        if self.phase == 'holding':
            return super().pending()
        self.check('refill-holding', self.phase, 'new learning remains under held reads')
        self.check(False, self.refill_qualified, 'remaining pending boundary is single-use')
        self.check(self.input_count, len(self.accepted), 'all actual acceptances mandatory')
        self.check(self.input_count, len(self.offered), 'all complete actual proposals mandatory')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'learning matured separately from acceptance')
        self.check(self.expected_plan, pending_plan(tage, TABLE, self.bank), 'each current result has its own latest version and service obligation')
        self.check(self.initial_overflows, tage.cache[TABLE, self.bank].overflows, 'no unserviced neighbor evicted')
        self.check((1, 1), tuple(map(len, self.written.values())), 'only the qualified first boundary serviced')
        self.refill_qualified, self.pending_ready = True, True
        self.reach(self.rules[3], actual_proposals=deepcopy(self.offered[3:]), expected_pending=self.expected_plan,
                   remaining_service_counts=tuple(map(len, self.expected_plan)))

    def consume(self, phase, name, source):
        self.check(True, phase in ('initial', 'mixed', 'blocked', 'serviced') and name in self.history_paths, 'declared visibility and history')
        self.check(False, (phase, name) in self.consumers, 'each required consumer compares once')
        wanted_phase = dict(initial='holding', mixed='mixed-holding', blocked='refill-holding', serviced='consuming')[phase]
        self.check(wanted_phase, self.phase, 'fresh consumer follows its declared lifecycle boundary')
        if phase == 'initial':
            self.check(True, self.pending_ready, 'initial learning qualified before old consumers')
            counts, after = (0, 0), self.accepted[-1][0]
        elif phase == 'mixed':
            counts, after = (1, 1), self.partial_end_tick
        elif phase == 'blocked':
            self.check(True, self.refill_qualified, 'late learning qualified before blocked consumers')
            counts, after = (1, 1), self.accepted[-1][0]
        else:
            counts, after = tuple(1 + len(p) for p in self.expected_plan), max(t for v in self.written.values() for t, _ in v)
        self.check(counts, tuple(map(len, self.written.values())), 'consumer has the exact actual service boundary')
        self.check(True, source.prediction_tick > after, 'consumer is genuinely fresh after its required boundary')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'consumer owns the same independent history')
        self.check(self.program.profile(phase, name), self.profile(source), 'complete Main/TAGE identity, counter and protection state')
        self.consumers[phase, name] = source
        if all((phase, n) in self.consumers for n in self.history_paths):
            rule = dict(initial=11, mixed=10, blocked=4, serviced=6)[phase]
            self.reach(self.rules[rule], consumers={n: dict(prediction_tick=self.consumers[phase, n].prediction_tick,
                meta_tick=self.consumers[phase, n].meta_tick, compared=self.profile(self.consumers[phase, n])) for n in self.history_paths})

    def release(self):
        self.check('refill-holding', self.phase, 'one final release after complete late learning')
        self.check(True, self.refill_qualified and all(('blocked', n) in self.consumers for n in self.history_paths),
                   'every mixed storage consumer required before final service')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def write_accepted(self, owner, transfer):
        partial = self.phase == 'partial-service'
        self.check(True, partial or self.phase == 'service', 'actual service belongs to a declared released window')
        self.check(True, owner in (0, 1), 'service owns a declared current owner')
        index = len(self.written[owner])
        self.check(True, index < (1 if partial else 1 + len(self.expected_plan[owner])), 'no suppressed, extra or duplicate service')
        self.check(True, transfer.accepted_tick > max(self.release_tick, self.offered[-1]['tick']), 'service follows release and all proposals')
        if partial:
            self.check(True, self.partial_candidate is not None, 'pre-edge public control prepared before acceptance')
            self.check(self.partial_candidate['tick'] + 1, transfer.accepted_tick, 'SDK confirms the exact prepared boundary')
            wanted = self.payload(FIRST_SERVICE[owner])
        else:
            wanted = self.expected_plan[owner][index - 1]
            if index > 1:
                self.check(self.written[owner][-1][0] + 2, transfer.accepted_tick, 'each owner independently drains adjacent results')
        self.check(wanted, transfer.value, 'complete SDK payload belongs to this logical identity and latest counter')
        self.check(True, isinstance(transfer.event, XEvent) and transfer.event.phase is XPhase.RISING_STABLE
                   and transfer.event.tick == transfer.accepted_tick, 'service has an actual SDK rising acceptance receipt')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))
        if partial and tuple(map(len, self.written.values())) == (1, 1):
            self.check(self.written[0][0][0], self.written[1][0][0], 'first two distinct identities serviced on the prepared boundary')
            self.partial_receipt.set_result(transfer.event)

    def services_complete(self):
        self.check('service', self.phase, 'final service qualification is single-use')
        self.check(tuple(1 + len(p) for p in self.expected_plan), tuple(map(len, self.written.values())),
                   'all declared results serviced; owner counts need not be equal')
        self.reach(self.rules[5], actual_writes=deepcopy(self.written), remaining_counts=tuple(map(len, self.expected_plan)))
        self.phase = 'consuming'

    def finish(self):
        self.check(False, self.closed, 'checked credit is single-use')
        self.check('consuming', self.phase, 'complete actual services mandatory')
        self.check({(p, n) for p in ('initial', 'mixed', 'blocked', 'serviced') for n in self.history_paths},
                   set(self.consumers), 'all twelve complete history consumers mandatory')
        self.check(self.input_frozen, tuple(s.meta for s in self.requests), 'every complete actually used original snapshot immutable')
        self.check(self.input_defined, tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                   for s in self.requests), 'every actually used independent source definition immutable')
        self.reach(self.rules[7], input_meta_ticks=[s.meta_tick for s in self.requests], compared_consumers=len(self.consumers))
        self.check(set(self.rules), self.completed, 'all semantic obligations required before checked')
        for rule in self.rules:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        self.closed = True
        retired = set()
        for s in (*self.requests, *self.sources, *self.saved.values(), *self.migration_before.values(),
                  *self.neighbor_before.values(), *self.before.values(), *self.consumers.values()):
            if s.meta_tick not in retired:
                self.pipeline.retire_source(s.meta_tick)
                retired.add(s.meta_tick)
