"""Exact logical-key hit/miss and deterministic sequential replacement checks."""
from copy import deepcopy

from suites.frontend.bpu.bpu.checker.dual_migration import DualMigrationChecks
from suites.frontend.bpu.bpu.coverage.partial_residency import RULES
from suites.frontend.bpu.bpu.model.tage.partial_residency import (
    PC, PATHS, POSITIONS, TABLE, PARTIAL_LABELS, PROGRAMS)
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight, pending_plan
from suites.frontend.bpu.tage.model.semantic import coordinate


class PartialResidencyChecks(DualMigrationChecks):
    def __init__(self, pipeline, coverage, program):
        if program not in PROGRAMS:
            raise ValueError('unknown partial-residency program')
        super().__init__(pipeline, coverage)
        self.program = program
        self.intents = tuple(program.preparation())
        self.saved, self.originals, self.definitions = {}, {}, {}
        self.stage_index, self.records, self.closed = -1, [], False

    @property
    def stage(self):
        return self.program.stages[self.stage_index]

    def preparing_input(self, source, step):
        if step.name not in PARTIAL_LABELS:
            return super().preparing_input(source, step)
        self.check(None, self.preparing, 'consume partial preparation before the next input')
        self.check(self.intents[len(self.prepared_labels)], step, 'declared partial preparation order')
        self.check(((0, False, False),), step.outcomes, 'only A is resolved; omitted B is not a not-taken result')
        matches = self.read(source).matches(POSITIONS[0])
        self.check(True, len(matches) == 1 and matches[0][2] < 4,
                   'provided A outcome agrees with its own genuine non-taken provider')
        self.preparing = source, step

    def save_source(self, name, source):
        self.check(True, name in self.program.source_names and name not in self.saved,
                   'each declared original source is captured once')
        self.check(self.program.source_profile(name), self.profile(source), 'original source has the declared old counters and owners')
        token = self.pipeline.source_token(source)
        self.check(True, all(token.history is not self.pipeline.source_token(s).history for s in self.saved.values()),
                   'each input uses a different original checkpoint')
        self.saved[name] = source
        self.originals[name] = deepcopy(source.meta)
        self.definitions[name] = deepcopy(self.pipeline.model.sources.defined_metadata(token))

    def arm(self, current):
        self.check(tuple(s.name for s in self.intents), tuple(self.prepared_labels), 'all normal preparation effects compared')
        self.check(set(self.program.source_names), set(self.saved), 'all genuine old sources captured')
        self.check(set(PATHS), set(current), 'both original and displaced histories required')
        for name, source in current.items():
            self.check(self.program.initial_profile(name), self.profile(source), 'partial residency has the exact declared prestate')
        old = self.read(next(iter(self.saved.values())))
        row, raw = coordinate(PC, old.context, TABLE)[1:]
        self.identities = {name: dict(row=row, valid=1, tag=raw ^ p)
                           for name, p in zip(('a', 'b'), POSITIONS, strict=True)}
        self.check(self.read(current['original']).context, old.context, 'old sources keep the original logical history')
        self.check(row, self.read(current['displaced']).rows[TABLE], 'the other genuine history shares this row')
        self.check(True, old.context != self.read(current['displaced']).context, 'the preserved neighbor is a different history')
        self.before, self.phase = current, 'qualified'
        self.reach(RULES[0], sources={n: dict(meta_tick=s.meta_tick, compared=self.profile(s))
            for n, s in self.saved.items()}, current={n: self.profile(s) for n, s in current.items()})

    def concrete(self, logical):
        return tuple(None if item is None else dict(self.identities[item[0]], counter=item[1]) for item in logical)

    def begin_stage(self, ordinal):
        self.check(self.stage_index + 1, ordinal, 'stages follow the declared semantic order')
        self.check('qualified' if self.stage_index < 0 else 'consuming', self.phase,
                   'each stage starts from qualified preparation or completed prior service')
        if self.stage_index >= 0:
            self.check({(p, n) for p in ('blocked', 'serviced') for n in PATHS}, set(self.consumers),
                       'every prior history consumer required before the next stage')
        self.check(True, ordinal < len(self.program.stages), 'no extra stage')
        self.stage_index = ordinal
        self.requests = tuple(self.saved[n] for n in self.stage.sources)
        self.input_ticks, self.offered, self.accepted, self.consumers = [], [], [], {}
        self.written, self.pending_ready, self.release_tick = {0: [], 1: []}, False, None
        self.expected_offers = tuple(self.concrete(p) for p in self.stage.proposals)
        service = self.concrete(self.stage.service)
        self.expected_plan = tuple(() if p is None else (p,) for p in service)
        self.initial_replacements = self.pipeline.model.sources.tage.cache[TABLE, self.bank].overflows
        self.check(((), ()), pending_plan(self.pipeline.model.sources.tage, TABLE, self.bank), 'no earlier pending version')
        self.records.append(dict(sources=self.stage.sources, accepted=[], offers=[], written=self.written,
                                 consumers=self.consumers))
        self.phase = 'armed'

    def begin_read_window(self):
        self.check('armed', self.phase, 'start one real held-read window per stage')
        self.phase = 'holding'

    def capture_state(self, event, packet):
        if self.failure is not None:
            return
        try:
            row = packet['state']
            self.last = event.tick, row
            self.check(0, row['reset'], 'reset cannot replace outstanding learning')
            self.check(0, row['reads'][1]['valid'], 'each old source qualifies without a training reread')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'read priority blocks SRAM services')
            if self.phase == 'holding':
                self.check(True, bool(busy), 'held window has uninterrupted real same-bank reads')
            if row['training']['valid'] and row['training']['ready']:
                self.check('holding', self.phase, 'feedback belongs to a declared held stage')
                p = row['prediction']
                self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank),
                           'actual prediction accepts beside each feedback')
                self.check(True, len(self.input_ticks) < len(self.stage.sources), 'no extra feedback')
                self.input_ticks.append(event.tick)
            ports = row['incoming']
            if any(p['valid'] for p in ports):
                self.check('holding', self.phase, 'complete proposal belongs to the current held window')
                index = len(self.offered)
                self.check(True, index < len(self.expected_offers) and index < len(self.input_ticks),
                           'exactly one proposal per genuine accepted source')
                actual = tuple(p['bits'] if p['valid'] else None for p in ports)
                self.check(self.expected_offers[index], actual, 'valid proposal ports and complete old-source payload')
                previous = (None, None) if index == 0 else self.stage.pending_after[index - 1]
                dirty = tuple(sum(v) for v in row['dirty'])
                self.check(tuple(int(p is not None) for p in previous), dirty, 'actual clean or pending victim prestate')
                hits = tuple((int(any(p['owner0'])), p['owner1']) for p in packet['owner_hits'])
                resident = self.program.name == 'resident-only' or (
                    self.program.name == 'evicted-pending-replace' and index == 0)
                self.check(((0, 1), (0, 0)) if resident else ((0, 0), (0, 0)), hits,
                           'actual full-key hit follows current owner; evicted identities are actual misses')
                self.check(True, event.tick > self.input_ticks[index], 'proposal follows its own actual input')
                if index:
                    self.check(self.offered[-1]['tick'] + 2, event.tick, 'proposals are truly adjacent')
                self.offered.append(dict(tick=event.tick, bits=deepcopy(actual), dirty=deepcopy(row['dirty']), hits=hits))
            if self.phase == 'holding' and self.pending_ready:
                self.check(tuple(int(bool(p)) for p in self.expected_plan), tuple(p['valid'] for p in row['writes']),
                           'only declared owner has a blocked service obligation')
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        self.check('holding', self.phase, 'original feedback accepted in its held stage')
        self.check((), tuple(self.accepted), 'the actual burst is consumed once')
        self.check(len(self.stage.sources), len(events), 'all declared original inputs accepted')
        for source, event, outcomes in zip(self.requests, events, self.stage.outcomes, strict=True):
            self.outcome(event, source, outcomes)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'genuine old source has nonreread qualification')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks), 'driver receipts equal actual public acceptances')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])),
                   'actual acceptance keeps both Main and TAGE enabled')
        if len(events) > 1:
            self.check(events[0][0] + 2, events[1][0], 'independent inputs accepted on adjacent cycles')
        self.accepted = list(events)
        self.records[-1]['accepted'] = list(self.input_ticks)

    def pending(self):
        self.check('holding', self.phase, 'pending evidence belongs to held read competition')
        self.check(False, self.pending_ready, 'pending qualification is single-use')
        self.check(len(self.stage.sources), len(self.accepted), 'actual original acceptances precede pending evidence')
        self.check(len(self.stage.sources), len(self.offered), 'every complete proposal observed')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'input completion is separate from mature learning')
        self.check(self.expected_plan, pending_plan(tage, TABLE, self.bank), 'latest complete logical pending identity')
        self.check(self.initial_replacements + self.stage.pending_replacements,
                   tage.cache[TABLE, self.bank].overflows, 'only declared same-destination pending replacement')
        self.check((0, 0), tuple(map(len, self.written.values())), 'no SDK service under held reads')
        self.records[-1]['offers'] = deepcopy(self.offered)
        self.records[-1]['expected_pending'] = deepcopy(self.expected_plan)
        self.pending_ready = True
        if self.stage_index == len(self.program.stages) - 1:
            self.reach(RULES[1], stages=[dict(sources=r['sources'], accepted=r['accepted']) for r in self.records])
            self.reach(RULES[2], proposals=[r['offers'] for r in self.records])
            self.reach(RULES[3], plans=[r['expected_pending'] for r in self.records],
                       pending_replacements=sum(s.pending_replacements for s in self.program.stages))

    def consume(self, phase, name, source):
        self.check(True, phase in ('blocked', 'serviced') and name in PATHS, 'declared consumer visibility and history')
        self.check(True, (phase, name) not in self.consumers, 'each consumer compares exactly once')
        if phase == 'blocked':
            self.check(True, self.phase == 'holding' and self.pending_ready, 'old storage read precedes release')
            self.check((0, 0), tuple(map(len, self.written.values())), 'no service before old visibility comparison')
            after = self.accepted[-1][0]
        else:
            self.check('consuming', self.phase, 'fresh consumer follows complete actual service')
            after = max(t for writes in self.written.values() for t, _ in writes)
        self.check(True, source.prediction_tick > after, 'consumer is a genuinely fresh query')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'consumer belongs to this exact history')
        self.check(self.program.profile(self.stage_index, name, serviced=phase == 'serviced'),
                   self.profile(source), 'full Main/TAGE identities, counters, useful and neighbor preservation')
        self.consumers[phase, name] = dict(prediction_tick=source.prediction_tick,
                                          meta_tick=source.meta_tick, compared=self.profile(source))
        if self.stage_index == len(self.program.stages) - 1 and all((phase, n) in self.consumers for n in PATHS):
            self.reach(RULES[4 if phase == 'blocked' else 6],
                       stages=[{n: r['consumers'][phase, n] for n in PATHS} for r in self.records])

    def release(self):
        self.check('holding', self.phase, 'release the current read window once')
        self.check(True, all(('blocked', n) in self.consumers for n in PATHS), 'both complete old-history consumers required')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def write_accepted(self, owner, transfer):
        self.check('service', self.phase, 'SDK service belongs to the released window')
        self.check(True, owner in (0, 1) and len(self.written[owner]) < len(self.expected_plan[owner]),
                   'no service of a victim, suppressed branch, old port or duplicate result')
        self.check(True, transfer.accepted_tick > self.release_tick and transfer.accepted_tick > self.offered[-1]['tick'],
                   'actual service follows every input and read release')
        self.check(self.expected_plan[owner][len(self.written[owner])], transfer.value,
                   'complete SDK payload uses the declared owner and latest complete logical version')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))

    def services_complete(self):
        self.check('service', self.phase, 'complete actual service is qualified once after release')
        self.check(tuple(map(len, self.expected_plan)), tuple(map(len, self.written.values())), 'all exact SDK services required')
        self.phase = 'consuming'
        if self.stage_index == len(self.program.stages) - 1:
            self.reach(RULES[5], stages=[r['written'] for r in self.records])

    def finish(self):
        self.check(False, self.closed, 'checked credit is single-use')
        self.check(len(self.program.stages), len(self.records), 'every declared stage executed')
        for record in self.records:
            self.check({(p, n) for p in ('blocked', 'serviced') for n in PATHS}, set(record['consumers']),
                       'every stage needs both old and new consumers for both histories')
        self.check(self.originals, {n: s.meta for n, s in self.saved.items()}, 'entire actual original metadata immutable')
        self.check(self.definitions, {n: self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                                     for n, s in self.saved.items()}, 'independently owned source definitions immutable')
        self.reach(RULES[7], sources={n: s.meta_tick for n, s in self.saved.items()},
                   consumers=sum(len(r['consumers']) for r in self.records))
        self.check(set(RULES), self.completed, 'every semantic obligation actually reached')
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        self.closed = True
        for source in self.saved.values():
            self.pipeline.retire_source(source.meta_tick)
