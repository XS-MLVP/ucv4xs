"""Independent pending history survives fresh-current then stale learning."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.dual_migration import DualMigrationChecks
from suites.frontend.bpu.bpu.coverage.neighbor_migration import RULES
from suites.frontend.bpu.bpu.model.tage.dual_migration import POSITIONS, TARGETS, TABLE
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import (
    PC, HISTORY_PATHS, OUTCOMES, OLD_SOURCE_COUNT, INPUT_NAMES, neighbor_preparation, expected_profile)
from suites.frontend.bpu.bpu.model.tage.service import pending_plan, learning_inflight
from suites.frontend.bpu.bpu.model.pipeline import Resolution, Outcome
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.tage.model.semantic import coordinate


class NeighborMigrationChecks(DualMigrationChecks):
    source_count = OLD_SOURCE_COUNT
    history_paths = HISTORY_PATHS
    neighbor_names = ('neighbor',)
    input_names = INPUT_NAMES
    rules = RULES
    history_profile = staticmethod(expected_profile)

    def neighbor_steps(self):
        return neighbor_preparation()

    @property
    def input_count(self):
        return len(self.neighbor_names) + 1 + self.source_count

    @property
    def service_count(self):
        return len(self.neighbor_names) + 1

    def __init__(self, pipeline, coverage):
        super().__init__(pipeline, coverage)
        self.neighbor_intents, self.neighbor_labels = tuple(self.neighbor_steps()), []
        self.neighbor_active, self.migration_before = None, None
        self.requests, self.input_frozen, self.input_defined = (), (), ()
        self.closed = False

    def neighbor_preparing(self, source, step):
        self.check('armed', self.phase, 'neighbor setup follows completed normal migration')
        self.check(None, self.neighbor_active, 'each neighbor effect has its own fresh consumer')
        self.check(self.neighbor_intents[len(self.neighbor_labels)], step, 'declared normal neighbor setup order')
        late = self.pipeline.model.sources.snapshot(self.pipeline.source_token(source), resolved=True).late.branch
        actual = next((POSITIONS[i] for i, taken, _ in step.outcomes if taken), None)
        predicted = late.position if late.taken else None
        wrong = None if actual == predicted else min(p for p in (actual, predicted) if p is not None)
        self.check(() if wrong is None else (wrong,), tuple(POSITIONS[i] for i, _, bad in step.outcomes if bad),
                   'normal neighbor wrong position follows the owned complete decision')
        self.neighbor_active = source, step

    def neighbor_prepared(self, source, step, event):
        self.check(True, self.neighbor_active is not None, 'neighbor input precedes its consumer')
        before, intended = self.neighbor_active
        self.check(intended, step, 'consumer belongs to this neighbor input')
        self.outcome(event, before, step.outcomes)
        self.check(True, source.prediction_tick > event[0], 'fresh post-learning neighbor query')
        self.check(step.expected, self.profile(source), f'hand-derived {step.context} state after {step.name}')
        self.neighbor_labels.append(step.name)
        self.neighbor_active = None

    def arm_neighbor(self, current):
        self.check('armed', self.phase, 'coexistence qualified once after migration')
        self.check(tuple(s.name for s in self.neighbor_intents), tuple(self.neighbor_labels), 'all declared normal neighbor effects completed')
        self.check(None, self.neighbor_active, 'no unconsumed neighbor preparation')
        self.check(set(self.history_paths), set(current), 'all declared distinct history consumers prepared')
        for name, source in current.items():
            self.check(((1, 3), self.history_profile(name, serviced=False)[1]), self.profile(source), 'shared Main and each pre-learning history state')
        for name in self.before:
            self.check(self.read(self.before[name]).context, self.read(current[name]).context, 'normal neighbor setup preserves target and displaced histories')
        target_row = self.proposal[0]['row']
        rows, contexts, self.side_payloads = dict(target=target_row), [], {}
        for name in self.neighbor_names:
            neighbor = self.read(current[name])
            self.check(True, all(neighbor.context != self.read(current[n]).context for n in ('original', 'displaced'))
                       and neighbor.context not in contexts, 'each neighbor owns a genuinely different history')
            contexts.append(neighbor.context)
            row, raw_tag = coordinate(PC, neighbor.context, TABLE)[1:]
            self.check(True, row not in rows.values(), 'each pending result uses its own history-derived row')
            rows[name] = row
            self.check(row, neighbor.rows[TABLE], 'neighbor row follows independent history geometry')
            tags = tuple(raw_tag ^ p for p in POSITIONS)
            self.check(tags, tuple(e.tag for e in neighbor.entries[TABLE]), 'neighbor tags follow the original instructions')
            self.side_payloads[name] = tuple(dict(row=row, valid=1, tag=tag, counter=c)
                for tag, c in zip(tags, (1, 6), strict=True))
        self.side_payload = self.side_payloads[self.neighbor_names[0]]
        fresh = (dict(self.proposal[1], counter=5), dict(self.proposal[0], counter=0))
        self.target_payload = (dict(self.proposal[1], counter=7), dict(self.proposal[0], counter=0))
        self.expected_offers = tuple(self.side_payloads[n] for n in self.neighbor_names) + (fresh, self.proposal, self.proposal)
        self.expected_plan = tuple(tuple(self.side_payloads[n][o] for n in self.neighbor_names) + (self.target_payload[o],)
                                   for o in range(2))
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'all setup effects matured before coexistence')
        self.check(((), ()), pending_plan(tage, TABLE, self.bank), 'no previous pending service can impersonate the experiment')
        cache = tage.cache[TABLE, self.bank]
        self.check((None, None), tuple(cache.find(target_row, p['tag']) for p in self.proposal),
                   'new fresh input is mandatory after normal eviction of clean target versions')
        self.initial_overflows = cache.overflows
        self.requests = (*(current[n] for n in self.neighbor_names), current['original'], *self.sources)
        tokens = tuple(self.pipeline.source_token(s) for s in self.requests)
        self.check(self.input_count, len({id(t.history) for t in tokens}), 'all declared input checkpoints genuinely distinct')
        for token in tokens:
            r = Resolution(token.history, PC, tuple(Outcome(POSITIONS[i], TARGETS[i], Kind.CONDITIONAL, taken,
                mispredict=wrong) for i, taken, wrong in OUTCOMES), origin=token)
            self.check(False, self.pipeline.model.sources.feedback_for(r).reread, 'each actual source independently qualifies without training reread')
        self.input_frozen = tuple(deepcopy(s.meta.resolve) for s in self.requests)
        self.input_defined = tuple(deepcopy(self.pipeline.model.sources.defined_metadata(t)) for t in tokens)
        self.migration_before, self.before, self.phase = self.before, current, 'neighbor-armed'
        witness = dict(target=self.profile(current['original']), neighbor=self.profile(current[self.neighbor_names[0]]),
                       rows=rows, fresh_current_mandatory=True)
        if len(self.neighbor_names) > 1:
            witness['neighbors'] = {n: self.profile(current[n]) for n in self.neighbor_names}
        self.reach(self.rules[1], **witness)

    def begin_read_window(self):
        self.check('neighbor-armed', self.phase, 'start one real read-competition window after both histories qualified')
        self.phase = 'holding'

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            self.last = event.tick, row
            self.check(False, bool(row['reset']), 'reset cannot replace independent pending effects')
            self.check(0, row['reads'][1]['valid'], 'all declared outcomes avoid a training SRAM reread')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'actual read competition blocks both services')
            if self.phase == 'holding':
                self.check(True, bool(busy), 'same-bank reads remain uninterrupted')
            if row['training']['valid'] and row['training']['ready']:
                self.check('holding', self.phase, 'only the declared coexistence inputs')
                self.check(True, len(self.input_ticks) < self.input_count, 'no extra original feedback')
                p = row['prediction']
                self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank), 'real prediction accepts beside each feedback')
                self.input_ticks.append(event.tick)
            ports = row['incoming']
            flags = tuple(p['valid'] for p in ports)
            self.check(True, flags in ((0, 0), (1, 1)), 'both logical branch proposals arrive together')
            if any(flags):
                self.check('holding', self.phase, 'every proposal belongs to the held learning window')
                index = len(self.offered)
                self.check(True, index < self.input_count and index < len(self.input_ticks), 'one complete proposal per accepted source')
                self.check(self.expected_offers[index], tuple(p['bits'] for p in ports), 'neighbor, fresh-current and old proposals keep their independent owners')
                self.check(True, len(row['dirty']) == 2 and all(len(v) == 4 for v in row['dirty']), 'complete actual retention prestate')
                dirty = tuple(sum(v) for v in row['dirty'])
                self.check((min(index, self.service_count),) * 2, dirty, 'neighbors first, then target, with no overwritten pending identity')
                self.check(True, event.tick > self.input_ticks[index], 'proposal follows its own public input')
                if index:
                    self.check(self.offered[-1]['tick'] + 2, event.tick, 'all complete proposals remain adjacent')
                self.observe_retained_hit(index, event, row)
                self.offered.append(dict(tick=event.tick, bits=tuple(p['bits'] for p in ports), dirty=dirty))
            if self.phase == 'holding' and self.pending_ready:
                self.check(((1, 0), (1, 0)), tuple((p['valid'], p['ready']) for p in row['writes']), 'both actual service fronts remain blocked')
        except Exception as error:
            self.failure = error

    def observe_retained_hit(self, index, event, row):
        """Profiles may require an additional actual retention precondition."""

    def accepted_burst(self, events):
        self.check('holding', self.phase, 'inputs accepted under actual read competition')
        self.check((), tuple(self.accepted), 'one coexistence burst')
        self.check(self.input_count, len(events), 'all neighbors, fresh target and both old targets actually accepted')
        for index, (source, event) in enumerate(zip(self.requests, events, strict=True)):
            self.outcome(event, source, OUTCOMES)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'each accepted outcome has its own nonreread source')
            if index:
                self.check(events[index - 1][0] + 2, event[0], 'actual inputs adjacent, not serialized effects')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks), 'public receipt order matches all independent sources')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])), 'both predictors enabled at acceptance')
        self.accepted.extend(events)
        self.reach(self.rules[2], sources=self.input_names, accepted_ticks=list(self.input_ticks), reread=False, prediction_concurrent=True)

    def pending(self):
        self.check(self.input_count, len(self.offered), 'all declared complete proposals mandatory')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'all learning matured separately from service')
        self.check(self.expected_plan, pending_plan(tage, TABLE, self.bank), 'closed-form neighbor and latest target results coexist under each current owner')
        self.check(self.initial_overflows, tage.cache[TABLE, self.bank].overflows, 'no pending logical result overwritten')
        self.check((0, 0), tuple(map(len, self.written.values())), 'no actual service before read release')
        self.pending_ready = True
        self.reach(self.rules[3], actual_proposals=deepcopy(self.offered), expected_pending=self.expected_plan, actual_commits=0)

    def consume(self, phase, name, source):
        self.check(True, phase in ('blocked', 'serviced') and name in self.history_paths, 'declared visibility and logical history')
        self.check(True, (phase, name) not in self.consumers, 'each required consumer compares once')
        if phase == 'blocked':
            self.check(True, self.phase == 'holding' and self.pending_ready, 'old consumer before any service release')
            self.check((0, 0), tuple(map(len, self.written.values())), 'old consumer has no preceding actual commit')
            after = self.accepted[-1][0]
        else:
            self.check('consuming', self.phase, 'fresh consumer after complete actual services')
            after = max(v[-1][0] for v in self.written.values())
        self.check(True, source.prediction_tick > after, 'query is genuinely fresh after its required boundary')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'consumer owns the exact declared history')
        self.check(self.history_profile(name, serviced=phase == 'serviced'), self.profile(source), 'complete Main/TAGE results and displaced-key misses')
        self.consumers[phase, name] = source
        if all((phase, n) in self.consumers for n in self.history_paths):
            witness = {n: dict(prediction_tick=self.consumers[phase, n].prediction_tick,
                meta_tick=self.consumers[phase, n].meta_tick, compared=self.profile(self.consumers[phase, n])) for n in self.history_paths}
            self.reach(self.rules[4 if phase == 'blocked' else 6], consumers=witness)

    def release(self):
        self.check('holding', self.phase, 'release one qualified read window')
        self.check(True, all(('blocked', n) in self.consumers for n in self.history_paths), 'all declared old histories consumed before release')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def write_accepted(self, owner, transfer):
        self.check('service', self.phase, 'actual service belongs to this release')
        self.check(True, owner in (0, 1), 'declared current owner')
        index = len(self.written[owner])
        self.check(True, index < self.service_count, 'each owner services every neighbor and target once')
        self.check(True, transfer.accepted_tick > self.release_tick and transfer.accepted_tick > self.offered[-1]['tick'], 'SDK service follows read release and every proposal')
        self.check(self.expected_plan[owner][index], transfer.value,
                   f'complete {self.input_names[index]} service for current owner {owner} keeps identity and latest counter')
        if index:
            self.check(self.written[owner][-1][0] + 2, transfer.accepted_tick, 'both pending identities service on adjacent cycles')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))

    def services_complete(self):
        self.check('service', self.phase, 'qualify complete services once')
        self.check((self.service_count,) * 2, tuple(map(len, self.written.values())), 'all declared actual full SDK services mandatory')
        self.check(tuple(t for t, _ in self.written[0]), tuple(t for t, _ in self.written[1]), 'both current owners preserve the same ordered service boundaries')
        self.reach(self.rules[5], actual_writes=deepcopy(self.written))
        self.phase = 'consuming'

    def finish(self):
        self.check(False, self.closed, 'final checked credit is single-use')
        self.check('consuming', self.phase, 'actual service qualification mandatory')
        self.check({(p, n) for p in ('blocked', 'serviced') for n in self.history_paths}, set(self.consumers), 'all declared visibility/history consumers mandatory')
        self.check(self.input_frozen, tuple(s.meta.resolve for s in self.requests), 'all actual original input snapshots immutable')
        self.check(self.input_defined, tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                   for s in self.requests), 'all independently owned input definitions immutable')
        self.reach(self.rules[7], input_meta_ticks=[s.meta_tick for s in self.requests], compared_consumers=2 * len(self.history_paths))
        self.check(set(self.rules), self.completed, 'every declared semantic obligation completed before checked')
        self.closed = True
        for rule in self.rules:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        for s in (*self.sources, *self.migration_before.values(), *self.before.values(), *self.consumers.values()):
            self.pipeline.retire_source(s.meta_tick)
