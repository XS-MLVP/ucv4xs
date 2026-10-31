"""Compare logical ownership, actual admission and both complete retirements."""
from copy import deepcopy
from toffee import CheckContext, ScoreboardMode
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.tage.dual_migration import (PC, POSITIONS, TARGETS, TABLE, SOURCE_COUNT,
                                                  PATHS, OUTCOMES, preparation, provider, counters_after)
from suites.frontend.bpu.bpu.model.tage.service import pending_plan, learning_inflight
from suites.frontend.bpu.tage.model.semantic import coordinate
from suites.frontend.bpu.bpu.coverage.dual_migration import RULES


class DualMigrationChecks:
    observe_retention = True
    source_count = SOURCE_COUNT

    def __init__(self, pipeline, coverage):
        self.pipeline, self.coverage = pipeline, coverage
        self.table, self.bank = TABLE, PC % 4
        self.phase, self.failure = 'preparation', None
        self.intents, self.prepared_labels = tuple(preparation()), []
        self.preparing, self.before = None, None
        self.sources, self.frozen, self.defined = [], [], []
        self.last, self.release_tick = None, None
        self.input_ticks, self.offered, self.accepted = [], [], []
        self.written, self.consumers = {0: [], 1: []}, {}
        self.pending_ready = False
        self.witnesses, self.completed = {}, set()

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure
        self.pipeline.raise_failure()

    def check(self, expected, actual, point):
        self.raise_failure()
        try:
            self.pipeline.board.check(expected=expected, actual=actual, context=CheckContext(
                self.pipeline.board.name, ScoreboardMode.DIRECT, request=dict(point=point, phase=self.phase,
                    prepared=self.prepared_labels, inputs=self.input_ticks, proposals=self.offered,
                    written=self.written, consumers=list(self.consumers))))
        except Exception as error:
            self.failure = error
            raise

    def reach(self, rule, **witness):
        self.completed.add(rule)
        self.witnesses[rule] = witness
        self.coverage.record('reached', rule, **witness)

    def read(self, source):
        return self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read

    def profile(self, source):
        token = self.pipeline.source_token(source)
        entries = tuple(e for row in source_entries(token.lookup) for e in row)
        read, main, tagged = self.read(source), [], []
        for position, target in zip(POSITIONS, TARGETS, strict=True):
            matches = tuple((slot, e) for slot, e in enumerate(entries) if e.hit and e.position == position)
            self.check(True, len(matches) <= 1, 'one logical Main record per original instruction')
            if matches:
                slot, entry = matches[0]
                self.check((1, 0, target), (entry.kind, entry.action, token.lookup.values()[f'{slot}.target']),
                           'complete conditional identity and full target preserved')
                main.append(entry.counter)
            else:
                main.append(None)
            providers = () if read is None else read.matches(position)
            self.check(True, len(providers) <= 1, 'only the declared longest-history provider, no alternate')
            tagged.append(providers[0] if providers else None)
        return tuple(main), tuple(tagged)

    def preparing_input(self, source, step):
        self.check(None, self.preparing, 'consume each preparation effect before the next')
        self.check(self.intents[len(self.prepared_labels)], step, 'declared semantic preparation order')
        late = self.pipeline.model.sources.snapshot(self.pipeline.source_token(source), resolved=True).late.branch
        actual = next((POSITIONS[i] for i, taken, _ in step.outcomes if taken), None)
        predicted = late.position if late.taken else None
        wrong = None if actual == predicted else min(p for p in (actual, predicted) if p is not None)
        self.check(() if wrong is None else (wrong,), tuple(POSITIONS[i] for i, _, bad in step.outcomes if bad),
                   'planned wrong position agrees with the owned complete decision')
        self.preparing = source, step

    def outcome(self, event, source, outcomes):
        tick, resolution = event
        self.check(True, tick > source.meta_tick and resolution.origin is self.pipeline.source_token(source),
                   'actual public feedback keeps its exact original source')
        wanted = PC, tuple((POSITIONS[i], TARGETS[i], 1, taken, wrong, 0) for i, taken, wrong in outcomes)
        actual = resolution.pc, tuple((b.position, b.target, int(b.kind), b.taken, b.mispredict, int(b.action))
                                      for b in resolution.branches if b is not None)
        self.check(wanted, actual, 'complete accepted branch vector and order')

    def prepared(self, source, step, event):
        self.check(True, self.preparing is not None, 'an actual input precedes each preparation consumer')
        before, intended = self.preparing
        self.check(intended, step, 'consumer closes its own declared input')
        self.outcome(event, before, step.outcomes)
        self.check(True, source.prediction_tick > event[0], 'fresh preparation consumer')
        self.check(step.expected, self.profile(source), 'hand-derived complete preparation state')
        self.prepared_labels.append(step.name)
        self.preparing = None

    def retain_old(self, source):
        self.check(True, len(self.sources) < self.source_count, 'only the declared distinct original predictions')
        self.check(((1, 3), (provider(0, 2), provider(1, 5))), self.profile(source), 'original two-provider state')
        token = self.pipeline.source_token(source)
        if self.sources:
            previous = self.sources[-1]
            self.check(True, previous.meta_tick < source.prediction_tick, 'different actual old queries')
            self.check(True, all(token is not self.pipeline.source_token(old) and
                                token.history is not self.pipeline.source_token(old).history for old in self.sources),
                       'different original checkpoint owners, not copied receipts')
            self.check(self.read(self.sources[0]), self.read(source), 'same original semantic content')
        fields = self.pipeline.model.sources.defined_metadata(token)
        for slot, e in enumerate(tuple(e for row in source_entries(token.lookup) for e in row)):
            if e.hit and e.position in POSITIONS:
                self.check((1, 0), (fields[f'{slot}.useProvider'], fields[f'{slot}.hasAlt']),
                           'both original providers independently qualify without SRAM reread')
        self.sources.append(source)
        self.frozen.append(deepcopy(source.meta.resolve))
        self.defined.append(deepcopy(fields))

    def arm(self, current):
        self.check(tuple(s.name for s in self.intents), tuple(self.prepared_labels), 'all normal preparation completed')
        self.check(self.source_count, len(self.sources), 'all declared old sources captured before migration')
        self.check(set(PATHS), set(current), 'original and displaced histories both observed')
        self.check(((0, 1), (provider(1, 1), provider(0, 4))), self.profile(current['original']),
                   'both original logical providers now have opposite owners and distinguishable counters')
        self.check(((0, 1), (None, None)), self.profile(current['displaced']), 'both displaced providers are absent')
        old, now, other = self.read(self.sources[0]), self.read(current['original']), self.read(current['displaced'])
        self.check(old.context, now.context, 'migration preserves original logical history')
        self.check(True, old.context != other.context, 'displaced path is a different genuine history')
        row = coordinate(PC, old.context, TABLE)[1]
        self.check((row, row, row), (old.rows[TABLE], now.rows[TABLE], other.rows[TABLE]),
                   'declared shared row comes from independent history geometry')
        tags = tuple(coordinate(PC, old.context, TABLE)[2] ^ position for position in POSITIONS)
        self.check(tags, tuple(e.tag for e in old.entries[TABLE]), 'old provider identities follow the declared original instructions')
        self.proposal = tuple(dict(row=row, valid=1, tag=tag, counter=c) for tag, c in zip(tags, (1, 6), strict=True))
        self.pending_payload = (dict(self.proposal[1], counter=6), dict(self.proposal[0], counter=0))
        self.clean_payload = (dict(self.proposal[1], counter=7), dict(self.proposal[0], counter=0))
        self.before, self.phase = current, 'armed'
        self.reach(RULES[0], old_owners=(0, 1), current_owners=(1, 0), original_counters=(2, 5), current_counters=(1, 4))

    def begin_read_window(self):
        self.check('armed', self.phase, 'start one actual read-pressure window after qualification')
        self.phase = 'holding'

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            self.last = event.tick, row
            self.check(False, bool(row['reset']), 'no reset can replace in-flight learning')
            self.check(0, row['reads'][1]['valid'], 'all original outcomes avoid a training SRAM reread')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'actual read priority blocks both writes')
            if self.phase == 'holding':
                self.check(True, bool(busy), 'uninterrupted actual same-bank reads')
            if row['training']['valid'] and row['training']['ready']:
                self.check(True, self.phase in ('holding', 'clean'), 'feedback belongs to a declared phase')
                if self.phase == 'holding':
                    p = row['prediction']
                    self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank),
                               'real prediction accepts beside each initial feedback')
                self.input_ticks.append(event.tick)
            ports = row['incoming']
            flags = tuple(p['valid'] for p in ports)
            self.check(True, flags in ((0, 0), (1, 1)), 'both opposed branch proposals arrive together')
            if any(flags):
                ordinal = len(self.offered)
                self.check(True, ordinal < SOURCE_COUNT and ordinal < len(self.input_ticks), 'one proposal per actual input')
                self.check(self.proposal, tuple(p['bits'] for p in ports), 'old proposals retain original ports, tags and counters')
                dirty = tuple(sum(way) for way in row['dirty'])
                self.check((1, 1) if ordinal == 1 else (0, 0), dirty, 'first clean, second pending, then serviced-clean input')
                self.check(True, event.tick > self.input_ticks[ordinal], 'proposal follows its own public input')
                if ordinal == 1:
                    self.check(self.offered[0]['tick'] + 2, event.tick, 'initial opposed proposals truly adjacent')
                self.offered.append(dict(tick=event.tick, bits=tuple(p['bits'] for p in ports), dirty=dirty))
            if self.phase == 'holding' and self.pending_ready:
                # Payload under !ready is not needed as a golden source.
                # Compare complete data only on SDK-confirmed retirement.
                self.check(((1, 0), (1, 0)), tuple((p['valid'], p['ready']) for p in row['writes']),
                           'both actual service obligations remain blocked')
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        self.check('holding', self.phase, 'initial accepts occur under read competition')
        self.check(2, len(events), 'two different old inputs accepted')
        self.check((), tuple(self.accepted), 'initial burst accepted once')
        for source, event in zip(self.sources[:2], events, strict=True):
            self.outcome(event, source, OUTCOMES)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'source-qualified nonreread feedback')
        self.check(events[0][0] + 2, events[1][0], 'actual adjacent input cycles')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks), 'all input receipts match the public monitor')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])), 'both predictors enabled')
        self.accepted.extend(events)
        self.reach(RULES[1], accepted_ticks=list(self.input_ticks), prediction_concurrent=True, reread=False)

    def pending(self):
        self.check(2, len(self.offered), 'both original proposals observed before pending qualification')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'acceptance is distinct from mature learning')
        self.check(tuple((p,) for p in self.pending_payload), pending_plan(tage, TABLE, self.bank),
                   'independently derived two current-owner pending versions')
        self.check((0, 0), tuple(map(len, self.written.values())), 'no actual commit under uninterrupted reads')
        self.pending_ready = True
        self.reach(RULES[2], initial_proposals=deepcopy(self.offered))
        self.reach(RULES[3], expected_pending=self.pending_payload, counter_rule=counters_after(2), actual_commits=0)

    def consume(self, phase, name, source):
        self.check(True, phase in ('blocked', 'serviced', 'clean') and name in PATHS, 'declared consumer phase and history')
        self.check(True, (phase, name) not in self.consumers, 'each required consumer compares once')
        if phase == 'blocked':
            self.check(True, self.phase == 'holding' and self.pending_ready, 'old consumer before service release')
            self.check((0, 0), tuple(map(len, self.written.values())), 'blocked consumer cannot follow any commit')
            counters, after = (1, 4), self.accepted[-1][0]
        else:
            count = 1 if phase == 'serviced' else 2
            self.check((count, count), tuple(map(len, self.written.values())), 'both actual owner retirements mandatory')
            counters, after = counters_after(2 if phase == 'serviced' else 3), max(v[-1][0] for v in self.written.values())
        self.check(True, source.prediction_tick > after, 'consumer is a fresh post-effect query')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'consumer keeps its exact history')
        wanted = (provider(1, counters[0]), provider(0, counters[1])) if name == 'original' else (None, None)
        self.check(((0, 3), wanted), self.profile(source), 'complete Main/TAGE consumer and displaced-key miss')
        self.consumers[phase, name] = source
        if phase == 'blocked' and all((phase, n) in self.consumers for n in PATHS):
            self.reach(RULES[4], consumers=self.consumer_witness(phase), actual_commits=0)
        elif phase == 'serviced' and all((phase, n) in self.consumers for n in PATHS):
            self.reach(RULES[5], actual_writes=deepcopy(self.written), consumers=self.consumer_witness(phase))
        elif phase == 'clean' and all((phase, n) in self.consumers for n in PATHS):
            self.reach(RULES[6], original_proposal=self.offered[2], actual_writes=deepcopy(self.written),
                       consumers=self.consumer_witness(phase))

    def consumer_witness(self, phase):
        return {name: dict(prediction_tick=self.consumers[phase, name].prediction_tick,
            meta_tick=self.consumers[phase, name].meta_tick, compared=self.profile(self.consumers[phase, name])) for name in PATHS}

    def release(self):
        self.check(True, all(('blocked', n) in self.consumers for n in PATHS), 'both old consumers before release')
        self.check('holding', self.phase, 'read pressure released once')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def write_accepted(self, way, transfer):
        self.check(True, self.phase in ('service', 'clean') and way in (0, 1), 'SDK retirement belongs to a service phase')
        ordinal = len(self.written[way])
        expected_ordinal = 0 if self.phase == 'service' else 1
        self.check(expected_ordinal, ordinal, 'each current owner retires once per phase')
        proposal_tick = self.offered[1 if self.phase == 'service' else 2]['tick']
        self.check(True, transfer.accepted_tick > proposal_tick and transfer.accepted_tick > self.release_tick,
                   'actual retirement follows learning and read release')
        payload = self.pending_payload if self.phase == 'service' else self.clean_payload
        self.check(payload[way], transfer.value, 'complete actual service belongs to current owner, not old port or counter')
        self.written[way].append((transfer.accepted_tick, deepcopy(transfer.value)))

    def begin_clean(self):
        self.check(True, all(('serviced', n) in self.consumers for n in PATHS), 'both committed consumers before reactivation')
        self.check('service', self.phase, 'clean phase starts once')
        self.phase = 'clean'

    def accepted_clean(self, event):
        self.outcome(event, self.sources[2], OUTCOMES)
        self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'third old source remains nonreread')
        self.check(3, len(self.input_ticks), 'exactly three distinct original inputs')
        self.check(event[0], self.input_ticks[2], 'reactivation actual acceptance matches its old source')
        self.accepted.append(event)

    def finish(self):
        self.check({(p, n) for p in ('blocked', 'serviced', 'clean') for n in PATHS}, set(self.consumers),
                   'all six real history/visibility consumers mandatory')
        self.check((2, 2), tuple(map(len, self.written.values())), 'all four actual complete owner services checked')
        self.check((3, 3, 3), (len(self.sources), len(self.accepted), len(self.offered)), 'three original sources consumed exactly once')
        self.check(tuple(self.frozen), tuple(s.meta.resolve for s in self.sources), 'all actual original metadata remain immutable')
        self.check(tuple(self.defined), tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                                            for s in self.sources), 'all independently owned old definitions remain immutable')
        self.reach(RULES[7], original_meta_ticks=[s.meta_tick for s in self.sources], compared_consumers=len(self.consumers))
        self.check(set(RULES), self.completed, 'every declared semantic obligation actually completed')
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        for source in (*self.sources, *self.before.values(), *self.consumers.values()):
            self.pipeline.retire_source(source.meta_tick)
