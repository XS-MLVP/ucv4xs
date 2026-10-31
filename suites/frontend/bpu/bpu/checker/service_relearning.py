"""Old service completion and new learning have distinct version obligations."""
from copy import deepcopy
from toffee import CheckContext, ScoreboardMode, XEvent, XPhase
from suites.frontend.bpu.bpu.checker.direction_service import DirectionServiceChecks
from suites.frontend.bpu.bpu.coverage.service_relearning import RULES
from suites.frontend.bpu.bpu.model.tage.forwarding import PC, POSITIONS, TARGETS
from suites.frontend.bpu.bpu.model.tage.service import pending_plan, learning_inflight
from suites.frontend.bpu.bpu.model.tage.service_relearning import PROGRAMS


class Checks(DirectionServiceChecks):
    observe_retention = True

    def __init__(self, pipeline, coverage, program):
        if program not in PROGRAMS: raise ValueError('declared learning coexistence program required')
        super().__init__(pipeline, coverage, program=program.service_program)
        self.profile = program
        self.phase = 'unarmed'
        self.offers, self.input_ticks, self.consumers = [], [], {}
        self.payloads, self.originals, self.definitions = (), (), ()
        self.receipt = self.prepared_event = self.candidate = self.collision = None
        self.remaining_plan = None

    def check(self, expected, actual, point):
        if self.failure is not None: raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected, actual=actual, context=CheckContext(
                self.pipeline.board.name, ScoreboardMode.DIRECT, sequence_id=self.pipeline.last_tick,
                request=dict(point=point, program=self.profile.name, phase=self.phase,
                    accepted=self.input_ticks, offers=self.offers, collision=self.collision,
                    services=self.written, last_actual=self.last)))
        except Exception as error:
            self.failure = error
            raise

    def reach(self, rule, **witness): self.coverage.record(rule, **deepcopy(witness))

    def arm(self, sources):
        super().arm(sources)
        by_history = {}
        for history, source in zip(self.program.feedback_order, sources, strict=True):
            read = self.pipeline.model.sources.snapshot(self.pipeline.source_token(source)).read
            by_history[history] = tuple(dict(row=read.rows[self.table], valid=1,
                tag=read.entries[self.table][owner].tag, counter=(1, 6)[owner]) for owner in range(2))
        self.payloads = tuple(by_history[i] for i in range(2))
        self.originals = tuple(deepcopy(s.meta) for s in sources)
        self.definitions = tuple(deepcopy(self.pipeline.model.sources.defined_metadata(
            self.pipeline.source_token(s))) for s in sources)
        self.phase = 'armed'
        self.reach(RULES[0], original_meta_ticks=[s.meta_tick for s in sources], original_counters=(2, 5))

    def originals_unchanged(self):
        self.check(self.originals, tuple(s.meta for s in self.sources), 'all real original metadata snapshots remain immutable')
        self.check(self.definitions, tuple(self.pipeline.model.sources.defined_metadata(
            self.pipeline.source_token(s)) for s in self.sources), 'independent original definitions are never rebased')

    def begin_read_window(self):
        self.check('armed', self.phase, 'read competition starts after source qualification')
        self.phase = 'initial-holding'

    def wanted_plan(self, *, remaining=False):
        result = []
        for owner in range(2):
            if not remaining:
                histories = self.profile.first_order
            elif self.profile.relation == 'other-identity':
                histories = (0,)
            else:
                histories = (0, 1) if self.profile.late_flags[owner] else (1,)
            result.append(tuple(dict(self.payloads[h][owner], counter=(
                self.profile.target[owner] if remaining and h == 0 else (1, 6)[owner])) for h in histories))
        return tuple(result)

    def check_records(self, packet, *, remaining=False):
        records, row = packet['records'], packet['state']
        self.check(True, len(records) == 2 and all(len(v) == 4 for v in records), 'complete current identity vectors required')
        wanted = self.wanted_plan(remaining=remaining)
        expected_dirty = {(owner, p['row'], p['valid'], p['tag']) for owner, values in enumerate(wanted) for p in values}
        actual_dirty = set()
        for owner, values in enumerate(records):
            for rank, record in enumerate(values):
                if row['dirty'][owner][rank]:
                    self.check(1, record['shadow'], 'a pending result always owns a retained identity')
                    actual_dirty.add((owner, record['row'], record['valid'], record['tag']))
        self.check(expected_dirty, actual_dirty, 'only the independently expected unfinished versions remain dirty')
        for history in range(2):
            for owner, key in enumerate(self.payloads[history]):
                matches = [record for record in records[owner] if record['shadow'] and
                    (record['row'], record['valid'], record['tag']) == (key['row'], key['valid'], key['tag'])]
                self.check(1, len(matches), 'one current retained version for each complete original identity')
                counter = self.profile.target[owner] if remaining and history == 0 else (1, 6)[owner]
                self.check(counter, matches[0]['counter'], 'current learning and unexecuted sibling retain their own counter')

    def capture_state(self, event, packet):
        if self.failure is not None: return
        try:
            self.last = event.tick, deepcopy(packet)
            row = packet['state']
            self.check(False, bool(row['reset']), 'reset cannot impersonate an old service completion')
            self.check(0, row['reads'][1]['valid'], 'all real original sources avoid training rereads')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy: self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'real prediction reads block both service ports')
            if self.phase in ('initial-holding', 'initial-pending', 'late-holding', 'remaining-held'):
                self.check(True, bool(busy), 'declared held phase has no hidden service opportunity')
            if row['training']['valid'] and row['training']['ready']:
                self.check(True, self.phase in ('initial-holding', 'late-holding'), 'only declared original feedback may accept')
                self.check(True, len(self.input_ticks) < 3, 'no extra accepted feedback')
                prediction = row['prediction']
                self.check(True, bool(prediction['valid'] and prediction['ready'] and prediction['pc'] % 4 == self.bank),
                    'real same-bank prediction accompanies feedback acceptance')
                self.input_ticks.append(event.tick)
            flags = tuple(p['valid'] for p in row['incoming'])
            if any(flags):
                index = len(self.offers)
                self.check(True, index < 3 and index < len(self.input_ticks), 'one proposal per genuinely accepted source')
                history = self.program.feedback_order[index]
                self.check((1, 1) if index < 2 else self.profile.late_flags, flags, 'only actually executed branches propose learning')
                for owner, port in enumerate(row['incoming']):
                    if port['valid']: self.check(self.payloads[history][owner], port['bits'], 'incoming complete payload retains its original query hint')
                self.check(True, event.tick > self.input_ticks[index], 'learning proposal follows its exact accepted source')
                if index == 2:
                    self.check('collision-window', self.phase, 'late learning must actually meet old service, not arrive before or after it')
                self.offers.append(dict(tick=event.tick, flags=flags, bits=deepcopy(row['incoming'])))
            if self.phase == 'remaining-held': self.check_records(packet, remaining=True)
        except Exception as error: self.failure = error

    def accepted_burst(self, events):
        self.check('initial-holding', self.phase, 'initial two-feedback burst compares once')
        self.check(2, len(events), 'one initial learning for each independent history')
        self.compare_acceptances(events, self.sources[:2])
        self.check(events[0][0]+2, events[1][0], 'initial feedbacks genuinely accept on adjacent cycles')
        self.accepted = tuple(events)

    def compare_acceptances(self, events, sources):
        for (tick, resolution), source in zip(events, sources, strict=True):
            self.check(True, resolution.origin is self.pipeline.source_token(source), 'actual accepted feedback has its exact original owner')
            path = self.profile.late_path if source is self.sources[2] else ((0, False, False), (1, True, False))
            expected = tuple((POSITIONS[i], TARGETS[i], int(taken), bool(wrong)) for i, taken, wrong in path)
            self.check(expected, tuple((b.position, b.target, int(b.taken), bool(b.mispredict))
                for b in resolution.branches if b is not None), 'accepted feedback is exactly the declared executed prefix')
            self.check(True, tick > source.meta_tick, 'feedback follows its genuine original metadata')

    def pending(self):
        self.check('initial-holding', self.phase, 'first independent cohort matures once')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'accepted input alone is not matured learning')
        self.check(2, len(self.offers), 'both actual first learning proposals mandatory')
        self.check(self.wanted_plan(), pending_plan(tage, self.table, self.bank), 'two independent old learning versions are pending')
        self.check_records(self.last[1])
        self.phase = 'initial-pending'
        self.reach(RULES[1], pending=self.wanted_plan(), actual_proposal_ticks=[v['tick'] for v in self.offers])

    def consume(self, phase, history, source):
        expected_phase = {'old': 'initial-pending', 'mixed': 'remaining-held', 'final': 'consuming'}[phase]
        self.check(expected_phase, self.phase, 'fresh consumer belongs to its actual visibility phase')
        self.check(True, history in (0, 1) and (phase, history) not in self.consumers, 'one genuine consumer per required history and phase')
        token, values = self.values(source)
        self.check(self.contexts[history], self.pipeline.model.sources.snapshot(token).read.context, 'consumer owns the exact original history')
        self.check(self.profile.counters(history, final=phase == 'final', mixed=phase == 'mixed'), values[1],
            'fresh consumer checks the independently expected old, mixed, or final storage value')
        self.check(((7, 0), (7, 1)), self.owners(token), 'both branch identities remain the original providers')
        self.check(((source.prediction_tick+2, 2),), self.pipeline.corrections_for_source(source), 'fresh consumer includes its complete compared repair window')
        after = self.accepted[-1][0] if phase == 'old' else max(v[-1][0] for v in self.written.values())
        self.check(True, source.prediction_tick > after, 'old receipts cannot impersonate a post-learning or post-service query')
        self.consumers[phase, history] = source
        if all((phase, h) in self.consumers for h in range(2)):
            if phase != 'final': self.reach(RULES[2 if phase == 'old' else 7], consumers=self.consumer_facts(phase))

    def consumer_facts(self, phase):
        return {str(h): dict(prediction_tick=self.consumers[phase, h].prediction_tick,
            meta_tick=self.consumers[phase, h].meta_tick) for h in range(2)}

    def late_accepted(self, event):
        self.check('late-holding', self.phase, 'late feedback accepts under uninterrupted read competition')
        self.compare_acceptances((event,), self.sources[2:])
        self.check(tuple(self.input_ticks), tuple(t for t, _ in (*self.accepted, event)), 'all compared acceptances match actual monitor events')
        self.accepted = (*self.accepted, event)
        self.reach(RULES[3], accepted_tick=event[0], executed_prefix=self.profile.late_path)

    def begin_late(self):
        self.check('initial-pending', self.phase, 'late learning follows qualified initial pending versions')
        self.check(True, all(('old', h) in self.consumers for h in range(2)), 'both old-storage consumers precede new learning')
        self.phase = 'late-holding'

    def begin_collision(self, receipt, prepared):
        self.check('late-holding', self.phase, 'open the service window only for the already accepted late source')
        self.check(3, len(self.accepted), 'late original input accepted before service window')
        self.check(2, len(self.offers), 'late learning must not have arrived before the service window')
        self.check((0, 0), tuple(map(len, self.written.values())), 'no hidden earlier service')
        self.receipt, self.prepared_event = receipt, prepared
        self.release_tick, self.phase = self.pipeline.last_tick, 'collision-window'

    def prepare_collision(self, event, packet):
        self.raise_failure()
        row = packet['state']
        if self.phase != 'collision-window' or not all(p['valid'] and p['ready'] for p in row['writes']): return
        self.check(True, isinstance(event, XEvent) and event.phase is XPhase.DRIVE_STABLE, 'public pre-edge preparation controls the rise-write window')
        self.check(False, self.prepared_event.done(), 'only one old service candidate')
        self.check(3, len(self.offers), 'actual late learning proposal has been compared before the candidate')
        self.check(self.profile.late_flags, tuple(p['valid'] for p in row['incoming']), 'new actual proposal must coexist with the old service candidate')
        self.check(tuple(v[0] for v in self.wanted_plan()), tuple(p['bits'] for p in row['writes']), 'old service candidate carries only old learned counters')
        for owner, port in enumerate(row['incoming']):
            if port['valid']: self.check(self.payloads[0][owner], port['bits'], 'pre-edge new learning retains the compared original payload')
        self.check_records(packet)
        self.candidate = dict(tick=event.tick, writes=deepcopy(row['writes']), incoming=deepcopy(row['incoming']))
        self.prepared_event.set_result(event)

    def write_accepted(self, owner, transfer):
        self.check(True, owner in (0, 1), 'actual service belongs to a declared logical owner')
        index = len(self.written[owner])
        overlap = self.phase == 'collision-window'
        self.check(True, overlap or self.phase == 'service', 'no service outside the two declared windows')
        plan = (self.wanted_plan()[owner][0],) if overlap else (self.wanted_plan()[owner][0], *self.remaining_plan[owner])
        self.check(True, index < len(plan), 'no duplicate or extra old/new service')
        self.check(plan[index], transfer.value, 'SDK confirms the complete independently expected old or new version')
        self.check(True, isinstance(transfer.event, XEvent) and transfer.event.phase is XPhase.RISING_STABLE
            and transfer.event.tick == transfer.accepted_tick, 'service requires its real SDK rising acceptance, not a candidate')
        if overlap:
            self.check(True, self.candidate is not None, 'old SDK service must meet an actually compared new learning candidate')
            self.check(self.candidate['tick']+1, transfer.accepted_tick, 'old service and new learning meet at the exact following SDK rising boundary')
            self.check(transfer.accepted_tick, self.last[0], 'current retained effects sampled at that same actual boundary')
            self.check_records(self.last[1], remaining=True)
            if self.collision is None:
                self.collision = dict(tick=transfer.accepted_tick, incoming=deepcopy(self.candidate['incoming']),
                    writes=deepcopy(self.candidate['writes']), dirty_after=deepcopy(self.last[1]['state']['dirty']))
            else: self.check(self.collision['tick'], transfer.accepted_tick, 'both old SDK services share the new learning boundary')
        else: self.check(True, transfer.accepted_tick > self.release_tick, 'remaining versions service only after final read release')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))
        if overlap and tuple(map(len, self.written.values())) == (1, 1): self.receipt.set_result(transfer.event)

    def collision_complete(self, event):
        self.check('collision-window', self.phase, 'collision window closes once')
        self.check((1, 1), tuple(map(len, self.written.values())), 'exactly one SDK-confirmed old result per owner')
        self.check(self.receipt.result(), event, 'window completion owns the same actual SDK receipt')
        self.check(True, self.collision is not None, 'real same-boundary learning is mandatory')
        self.phase = 'remaining-held'
        self.remaining_plan = self.wanted_plan(remaining=True)
        self.check(self.profile.remaining, tuple(map(len, self.remaining_plan)), 'new versus untouched siblings have independent service obligations')
        self.check(self.remaining_plan, pending_plan(self.pipeline.model.sources.tage, self.table, self.bank), 'old completion cannot discharge new learning')
        self.check_records(self.last[1], remaining=True)
        self.originals_unchanged()
        self.reach(RULES[4], candidate=self.candidate, actual=self.collision, SDK_services=self.written)
        self.reach(RULES[5], remaining=self.remaining_plan, actual_tick=self.last[0])
        self.reach(RULES[6], target=self.profile.target, neighbor=(1, 6), executed_prefix=self.profile.late_path)

    def release(self):
        self.check('remaining-held', self.phase, 'final release follows real collision closure')
        self.check(True, all(('mixed', h) in self.consumers for h in range(2)), 'both mixed-visibility consumers must compare before release')
        self.release_tick, self.phase = self.pipeline.last_tick, 'service'

    def services_complete(self):
        self.check('service', self.phase, 'remaining SDK services complete once')
        self.check(tuple(1+n for n in self.profile.remaining), tuple(map(len, self.written.values())), 'all and only remaining obligations actually retire')
        self.check(((), ()), pending_plan(self.pipeline.model.sources.tage, self.table, self.bank), 'no unfinished old or new version after real service')
        self.reach(RULES[8], actual_services=self.written)
        self.phase = 'consuming'

    def finish(self):
        self.check(False, self.closed, 'cohort checked credit is single-use')
        self.check('consuming', self.phase, 'all real services precede final consumers')
        self.check({(p, h) for p in ('old', 'mixed', 'final') for h in range(2)}, set(self.consumers), 'all six independent consumers mandatory')
        self.check((0, 0), tuple(p['valid'] for p in self.last[1]['state']['writes']), 'no extra pending write after final consumers')
        self.originals_unchanged()
        self.reach(RULES[9], consumers=self.consumer_facts('final'), original_meta_ticks=[s.meta_tick for s in self.sources])
        self.coverage.finish()
        self.closed = True
        for source in (*self.sources, *self.consumers.values()): self.pipeline.retire_source(source.meta_tick)

    def snapshot(self):
        return deepcopy(dict(program=self.profile.name, phase=self.phase, closed=self.closed,
            accepted_ticks=self.input_ticks, actual_proposals=self.offers, candidate=self.candidate,
            collision=self.collision, actual_services=self.written, remaining_plan=self.remaining_plan,
            consumers={p:self.consumer_facts(p) for p in ('old', 'mixed', 'final')
                if all((p, h) in self.consumers for h in range(2))},
            original_meta_ticks=[s.meta_tick for s in self.sources],
            first_failure=None if self.failure is None else str(self.failure),
            full_FTQ_source_eligibility_proved=False))
