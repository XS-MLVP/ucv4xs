"""Separate original eligibility, current effects and actual service receipts."""
from copy import deepcopy
from toffee import CheckContext, ScoreboardMode
from bpuverify.bpu.checker.direction_forwarding import DirectionForwardingChecks
from bpuverify.bpu.model.tage.forwarding import PC, POSITIONS, TARGETS
from bpuverify.bpu.model.tage.service import learning_inflight, pending_plan
from bpuverify.bpu.model.tage.selective_learning import ALL_PROGRAMS, RULES


class Checks(DirectionForwardingChecks):
    observe_retention = True

    def __init__(self, pipeline, coverage, program):
        if program not in ALL_PROGRAMS: raise ValueError('declared selective-learning program required')
        super().__init__(pipeline, coverage)
        self.program = program
        self.table, self.bank = 7, PC % 4
        self.holding = False
        self.keys, self.contexts, self.originals, self.definitions = (), (), (), ()
        self.counts = [0]*len(program.paths)
        self.offers, self.inputs, self.written, self.boundaries, self.consumers = [], [], [], [], {}
        self.batch, self.batch_events = (), ()
        self.wave = 0
        self.wave_plan = None
        self.wave_writes = []
        self.release_tick = None
        self.last = None
        self.recovery = []
        self.last_packet = None

    def check(self, expected, actual, point):
        if self.failure is not None: raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected, actual=actual, context=CheckContext(
                self.pipeline.board.name, ScoreboardMode.DIRECT, sequence_id=self.pipeline.last_tick,
                request=dict(point=point, program=self.program.name, counts=self.counts,
                    accepted_ticks=[t for t, _ in self.accepted], actual_boundary=self.boundaries,
                    last_actual_state=self.last_packet)))
        except Exception as error:
            self.failure = error
            raise

    def arm(self, sources):
        self.check((), self.sources, 'one cohort of old original owners')
        self.check(len(self.program.feedback_order), len(sources), 'one distinct real original per late feedback')
        reads = []
        for source in sources:
            token, values = self.values(source)
            self.check(((0, 3), self.program.initial), values, 'qualified branch and saturated companion established by real learning')
            self.check(((7, 0), (7, 1)), self.owners(token), 'two independent longest-history providers')
            reads.append(self.pipeline.model.sources.snapshot(token).read)
        self.check(len(sources), len({id(self.pipeline.source_token(s).history) for s in sources}), 'original owners are never cloned')
        ordered = reads[:len(self.program.paths)]
        self.check(len(ordered), len({r.context for r in ordered}), 'semantic paths have distinct original histories')
        self.check(len(ordered), len({r.rows[self.table] for r in ordered}), 'independent histories retain different destinations')
        for h, read in zip(self.program.feedback_order, reads, strict=True):
            self.check(ordered[h], read, 'revisited source keeps the exact immutable old history and content')
        self.contexts = tuple(r.context for r in ordered)
        self.keys = tuple(tuple(dict(row=r.rows[self.table], valid=1, tag=r.entries[self.table][o].tag) for o in range(2)) for r in ordered)
        self.sources = tuple(sources)
        self.originals = tuple(deepcopy(s.meta) for s in sources)
        self.definitions = tuple(deepcopy(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))) for s in sources)
        self.coverage.compare(RULES[0], sources[-1].meta_tick)

    def originals_unchanged(self):
        self.check(self.originals, tuple(s.meta for s in self.sources), 'actual original metadata remains immutable')
        self.check(self.definitions, tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s)) for s in self.sources),
            'reference originals are not rebased to current counters')

    def raise_failure(self):
        if self.failure is not None: raise self.failure
        self.pipeline.raise_failure()

    def begin_read_window(self):
        self.check(False, self.holding, 'a read-priority window starts only once per wave')
        self.holding = True

    def begin_batch(self, indices):
        self.check((), self.batch, 'previous batch must finish before another actual learning boundary')
        self.batch = tuple(indices)
        self.batch_events = ()
        self.wave_plan = None
        self.wave_writes = []
        self.release_tick = None

    def current_record(self, records, history, owner, *, required=True):
        key = self.keys[history][owner]
        matches = [(rank, r) for rank, r in enumerate(records[owner]) if r['shadow'] and
            {k: r[k] for k in key} == key]
        self.check(True, len(matches) == 1 if required else len(matches) <= 1,
            'a learned identity has one current record; a clean unreferenced cache record may be reused')
        return matches[0] if matches else None

    def capture_state(self, event, packet):
        if self.failure is not None: return
        try:
            row, records = packet['state'], packet['records']
            active, companion_owner = self.program.active, 1-self.program.active
            self.last = event.tick, row
            self.last_packet = deepcopy(packet)
            if not self.holding: return
            self.check(0, row['reset'], 'reset cannot erase a live cohort')
            self.check(True, any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads']), 'uninterrupted genuine read priority')
            self.check(0, row['reads'][1]['valid'], 'these correct old outcomes do not require a training reread')
            self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'both SRAM write ports are actually blocked')
            if row['training']['valid'] and row['training']['ready']:
                self.check(True, bool(row['prediction']['valid'] and row['prediction']['ready']), 'real prediction and feedback accepted together')
                self.inputs.append(event.tick)
            self.check(0, row['incoming'][companion_owner]['valid'], 'absent or saturated companion cannot borrow the qualified branch eligibility')
            if row['incoming'][active]['valid']:
                ordinal = len(self.offers)
                self.check(True, ordinal < len(self.program.feedback_order), 'no unrequested qualified-branch proposal')
                history = self.program.feedback_order[ordinal]
                retained = self.current_record(records, history, active, required=self.counts[history] > 0)
                if retained is not None:
                    rank, current = retained
                    self.check(self.program.counters(history, self.counts[history])[active], current['counter'],
                        'old learning applies to its own latest retained counter')
                expected = dict(self.keys[history][active], counter=self.program.proposal)
                self.check(expected, row['incoming'][active]['bits'], 'qualified old original proposes independently of current-boundary numerical hold')
                if self.counts[history] == 2:
                    self.boundaries.append(dict(tick=event.tick, original=self.program.original, current=current['counter'], proposal=self.program.proposal,
                        pending=row['dirty'][active][rank], companion_valid=row['incoming'][companion_owner]['valid'], wave=self.wave))
                    self.coverage.compare(RULES[2], event.tick)
                self.counts[history] += 1
                self.offers.append(dict(tick=event.tick, history=history, bits=deepcopy(expected)))
            self.check((0,)*4, tuple(row['dirty'][companion_owner]), 'no pending service for an inactive companion')
            for history in range(len(self.program.paths)):
                retained = self.current_record(records, history, companion_owner, required=False)
                if retained is not None:
                    _, companion = retained
                    self.check(self.program.initial[companion_owner], companion['counter'], 'nonparticipating companion keeps its own saturated value')
            if self.wave_plan is not None: self.check_fronts(row)
        except Exception as error: self.failure = error

    def accepted_burst(self, events):
        self.check(len(self.batch), len(events), 'every requested feedback has a compared actual acceptance')
        for index, (source_index, (tick, resolution)) in enumerate(zip(self.batch, events, strict=True)):
            source = self.sources[source_index]
            self.check(True, resolution.origin is self.pipeline.source_token(source), 'acceptance belongs to its immutable original owner')
            expected = tuple((POSITIONS[i], TARGETS[i], 1, taken, wrong, 0) for i, taken, wrong in self.program.outcome)
            actual = tuple((b.position, b.target, int(b.kind), b.taken, b.mispredict, int(b.action)) for b in resolution.branches if b is not None)
            self.check((PC, expected), (resolution.pc, actual), 'only the declared semantic branch results participate')
            if index: self.check(events[index-1][0]+2, tick, 'burst inputs actually accept on adjacent clock cycles')
            self.check(True, tick > source.meta_tick, 'each late result follows the real source')
        self.accepted += tuple(events)
        self.batch_events = tuple(events)
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])),
            'both Main and TAGE really enabled on the accepted feedback')
        self.check(tuple(t for t, _ in self.accepted), tuple(self.inputs), 'complete monitored input receipt list')
        self.coverage.compare(RULES[1], events[-1][0])

    def check_fronts(self, row):
        for owner, expected in enumerate(self.wave_plan):
            self.check(int(bool(expected)), row['writes'][owner]['valid'], 'all and only qualified owners have a pending service')
            if expected: self.check(expected[0], row['writes'][owner]['bits'], 'full oldest service payload remains stable')

    def pending(self):
        self.raise_failure()
        self.check(False, learning_inflight(self.pipeline.model.sources.tage), 'all accepted effects have matured')
        self.check(len(self.accepted), len(self.offers), 'every qualified input produces exactly one full proposal')
        histories = tuple(dict.fromkeys(self.program.feedback_order[i] for i in self.batch))
        active = self.program.active
        plan = pending_plan(self.pipeline.model.sources.tage, self.table, self.bank)
        expected = {(self.keys[h][active]['row'], self.keys[h][active]['tag']): dict(self.keys[h][active],
            counter=self.program.counters(h, self.counts[h])[active]) for h in histories}
        self.check(expected, {(p['row'], p['tag']): p for p in plan[active]}, 'closed-form history-specific accumulated counters qualify the model plan')
        self.check(tuple(len(histories) if owner == active else 0 for owner in range(2)), tuple(map(len, plan)),
            'no inactive-companion write or lost qualified-branch service')
        self.wave_plan = deepcopy(plan)
        self.check_fronts(self.last[1])
        self.originals_unchanged()

    def consume(self, phase, history, source, counters):
        token, values = self.values(source)
        self.check(self.contexts[history], self.pipeline.model.sources.snapshot(token).read.context, 'fresh consumer belongs to original history')
        self.check(((0, 3), tuple(counters)), values, 'new public consumer agrees with hand-derived per-branch effects')
        self.check(((7, 0), (7, 1)), self.owners(token), 'provider identities survive selective learning')
        key = phase, history
        self.check(False, key in self.consumers, 'one separately checked consumer for this phase and history')
        self.check(True, source.prediction_tick > self.accepted[-1][0], 'old source receipt cannot replace a post-feedback consumer')
        if phase.startswith('new'):
            self.check(True, self.wave_serviced(), 'all actual services precede new visibility')
            self.check(True, source.prediction_tick > self.written[-1]['tick'], 'consumer follows the last actual service')
        else:
            self.check(True, self.holding, 'old-value consumer must precede read release')
        self.consumers[key] = source
        self.originals_unchanged()
        self.coverage.compare(RULES[3] if phase.startswith('old') else RULES[5], source.meta_tick)

    def release(self):
        self.check(True, self.wave_plan is not None and self.holding, 'pending effects checked before actual read release')
        self.holding = False
        self.release_tick = self.pipeline.last_tick

    def write_accepted(self, owner, transfer):
        self.check(True, self.release_tick is not None and transfer.accepted_tick > self.release_tick, 'no service can bypass read priority')
        self.check(self.program.active, owner, 'inactive companion must never emit a service')
        ordinal = len(self.wave_writes)
        self.check(True, ordinal < len(self.wave_plan[owner]), 'no duplicate or extra service')
        self.check(self.wave_plan[owner][ordinal], transfer.value, 'complete owner payload and independent service order')
        receipt = dict(tick=transfer.accepted_tick, owner=owner, bits=deepcopy(transfer.value), wave=self.wave)
        self.wave_writes.append(receipt)
        self.written.append(receipt)

    def wave_serviced(self): return self.wave_plan is not None and len(self.wave_writes) == len(self.wave_plan[self.program.active])

    def services_complete(self):
        self.check(True, self.wave_serviced(), 'every exact expected service has a real receipt')
        self.check(((), ()), pending_plan(self.pipeline.model.sources.tage, self.table, self.bank), 'no unconsumed version after release')
        self.coverage.compare(RULES[4], self.pipeline.last_tick)
        self.batch = ()
        self.wave += 1

    def recovered(self, steps, preserved):
        self.check(2, len(steps), 'reverse learning and restoration both need an actual input and a new consumer')
        for index, (source, event, after) in enumerate(steps):
            tick, resolution = event
            self.check(True, resolution.origin is self.pipeline.source_token(source), 'recovery input retains its own real source')
            self.check(True, tick > source.meta_tick and after.prediction_tick > tick, 'recovery consumer follows its actual feedback')
            outcome = self.program.reverse_outcome if index == 0 else self.program.restore_outcome
            expected = tuple((POSITIONS[i], TARGETS[i], 1, taken, wrong, 0) for i, taken, wrong in outcome)
            actual = tuple((b.position, b.target, int(b.kind), b.taken, b.mispredict, int(b.action)) for b in resolution.branches if b is not None)
            self.check((PC, expected), (resolution.pc, actual), 'reverse and restoration retain the complete actually executed NT prefix')
            token = self.pipeline.source_token(source)
            self.check(self.contexts[self.program.target], self.pipeline.model.sources.snapshot(token).read.context,
                'reverse and restore remain in the original selected history')
            final = ((0, 3), self.program.counters(self.program.target, self.counts[self.program.target]))
            self.prepared(source, final if index == 0 else self.program.reversed_values)
            self.prepared(after, self.program.reversed_values if index == 0 else final)
            self.recovery.append(dict(accepted_tick=tick, source_tick=source.meta_tick, consumer_tick=after.meta_tick,
                branches=actual))
        self.check(len(self.program.paths), len(preserved), 'every unrelated history needs a post-restoration consumer')
        for history, source in enumerate(preserved):
            token, _ = self.values(source)
            self.check(self.contexts[history], self.pipeline.model.sources.snapshot(token).read.context, 'preservation query owns the correct history')
            self.prepared(source, ((0, 3), self.program.counters(history, self.counts[history])))
        self.originals_unchanged()
        self.coverage.compare(RULES[6], preserved[-1].meta_tick)

    def finish(self):
        self.raise_failure()
        self.check(tuple(self.program.feedback_order.count(h) for h in range(len(self.program.paths))), tuple(self.counts), 'all distinct sources actually learned')
        self.check(1, len(self.boundaries), 'one genuine old-source/current-boundary hold')
        self.check(2, len(self.recovery), 'reverse learning is required, not inferred from an unchanged boundary')
        self.check(int(self.program.boundary == 'still-pending'), self.boundaries[0]['pending'], 'hold occurs on the declared pending or already-serviced version')
        phases = ('old-first', 'new-first') + (() if self.program.boundary == 'still-pending' else ('old-held', 'new-held'))
        self.check({(phase, h) for phase in phases for h in range(len(self.program.paths))}, set(self.consumers), 'all histories and every visibility boundary consumed')
        self.originals_unchanged()
        self.coverage.compare(RULES[7], self.pipeline.last_tick)
        self.coverage.finish(self.pipeline.last_tick)
        self.closed = True
        for source in (*self.sources, *self.consumers.values()): self.pipeline.retire_source(source.meta_tick)

    def snapshot(self):
        return deepcopy(dict(program=self.program.name, direction=self.program.direction, active_position=POSITIONS[self.program.active],
            initial_counters=self.program.initial, closed=self.closed, original_ticks=[s.meta_tick for s in self.sources],
            accepted_ticks=[t for t, _ in self.accepted], proposals=self.offers, boundaries=self.boundaries,
            services=self.written, counts=self.counts,
            recovery=self.recovery,
            last_actual_state=None if self.failure is None else self.last_packet,
            consumers={phase+'.'+str(h): dict(prediction_tick=s.prediction_tick, meta_tick=s.meta_tick) for (phase, h), s in self.consumers.items()},
            first_failure=None if self.failure is None else str(self.failure), full_FTQ_eligibility_proved=False))
