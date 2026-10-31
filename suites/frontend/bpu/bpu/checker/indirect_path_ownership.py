"""Measured actual effects and atomic closure share one contextual scoreboard."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
from toffee import XEvent, XPhase
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.coverage.indirect_path_ownership import Coverage
from suites.frontend.bpu.bpu.model.indirect_path_ownership import PHASES, RULES, resolution, layout
from suites.frontend.bpu.bpu.model.early_opposition import provider, resident
from suites.frontend.bpu.bpu.model.path_history import WIDTH, SHIFT, path_contribution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.utage.model.semantic import Entry, tag


class _ObservedChecks(EarlyDirectionChecks):
    def __init__(self, profile):
        self.program = layout(profile)
        super().__init__(None, self.program.b)
        self.plans, self.inputs, self.saved, self.offers = {}, [], {}, {}
        self.seed = self.stable = self.target_control = None
        self.acceptance = self.selected = self.selected_tick = None
        self.middle = self.repair = self.pending = self.confirmed = None
        self.restored = self.new_a = self.new_b = None
        self.facts = {}
        self.redirect_count = 0
        self.last_redirect = None

    def snapshots(self, token):
        bank = self.pipeline.model.sources
        return (bank.snapshot(token), bank.short_snapshot(token), bank.tage_snapshot(token),
            bank.tage_snapshot(token, resolved=True), bank.target_snapshot(token),
            bank.target_snapshot(token, resolved=True))

    def save(self, source):
        token = self.pipeline.source_token(source)
        self.check(True, self.pipeline.model.published.get(token.sequence) is token, 'exact original receipt')
        self.saved.setdefault(source.meta_tick, (source, token, self.snapshots(token), deepcopy(source.meta)))
        return token

    def plan_resolution(self, phase, source):
        self.check(PHASES[len(self.plans)], phase, 'nine real outcomes in declared semantic order')
        token = self.save(source)
        self.check(resolution(self.program, phase)[0], token.pc, 'normal feedback uses the declared block')
        self.plans[phase] = source

    def early_consumer(self, source):
        token = self.save(source)
        self.check((self.program.b, 2, int(Kind.CONDITIONAL), self.program.a),
            (token.pc, token.early.branch.position, int(token.early.branch.kind), token.early.branch.target),
            'real early conditional experience precedes the target conflict')
        self.seed = source

    def stable_predecessor(self, source):
        from suites.frontend.bpu.tage.model.semantic import HISTORIES
        token = self.save(source)
        self.check(self.program.stable_predecessor_history, token.history.history % (1 << max(HISTORIES)),
            'natural two-block path establishes the target context')
        self.stable = source

    def target_consumer(self, source):
        token = self.save(source)
        value = self.pipeline.model.sources.target_snapshot(token, resolved=True).prediction
        self.check(True, value is not None and value.provider is not None, 'independently learned target provider')
        self.check((self.program.a, 3), (value.target // 2, value.confidence), 'target original is strong before Main changes')
        self.target_control = source

    def open(self):
        self.check(True, all(value is not None for value in (self.seed, self.stable, self.target_control)),
            'early original, stable predecessor and independent target all required')
        self.acceptance = asyncio.get_running_loop().create_future()
        return self.acceptance

    def candidates(self, row, events, cycle, model, phase, previous):
        self.events, self.cycle = events, cycle
        self.actual_useful = row['observed']['early_direction']['useful']
        self.applied = model.sources.short.learning
        self.candidate = None
        first = cycle.tokens[0]
        if self.acceptance is not None and not self.acceptance.done() and first is not None:
            early = cycle.decisions[0]
            if first.pc == self.pc and cycle.fires[1] and not cycle.flushes[0] and early.branch.position == 2:
                branches, wanted, _ = model.sources.tage_decision(first)
                indirect = any(branch is not None and branch.position == 4
                    and branch.kind == Kind.INDIRECT and branch.target == self.program.a + 0x200 for branch in branches)
                if early.source in ('ahead', 'ahead-direction') and early.branch.taken and indirect:
                    self.candidate = first
        return ()

    def reached(self, tick, *candidates):
        pass

    def accepted_feedback(self, request, tick):
        phase = next((name for name, source in self.plans.items()
            if self.pipeline.source_token(source) is request.origin), None)
        self.check(True, phase is not None, 'only a planned complete original may train')
        branch, = tuple(branch for branch in request.branches if branch is not None)
        self.check(resolution(self.program, phase), (request.pc, branch.position, branch.target,
            int(branch.kind), branch.taken, branch.mispredict), 'complete branch outcome, not table programming')
        self.inputs.append(dict(phase=phase, owner=request.origin.sequence, tick=tick))

    def check_consumer(self, token):
        self.check((4, int(Kind.INDIRECT)), (token.early.branch.position, int(token.early.branch.kind)),
            'new NT direction selects the actual later indirect')
        self.check(self.program.a, self.pipeline.model.sources.target_snapshot(token, resolved=True).late.branch.target,
            'new consumer still owns the correct indirect target')

    def checked(self, tick, *candidates):
        model = self.pipeline.model
        bank, cycle, events = model.sources, self.cycle, self.events
        if events.redirect is not None:
            self.redirect_count += 1
            self.last_redirect = (tick, events.redirect.source, events.prediction_ready)
        if self.pending is not None:
            record = self.pending
            self.check(record['written_tick'] + 2, tick, 'next complete actual-state comparison')
            self.check(1, self.actual_useful[0][record['index']], 'actual protection belongs to original short teacher')
            self.confirmed = dict(record, confirmed_tick=tick)
            self.pending = None
        if events.feedback is not None:
            self.accepted_feedback(events.feedback,tick)
        if self.candidate is not None:
            event = self.pipeline.current_event
            self.check(True, isinstance(event, XEvent) and event.phase is XPhase.RISING_STABLE and event.tick == tick,
                'driver release uses the real already-compared S1 event')
            self.selected, self.selected_tick = self.candidate, tick
            self.acceptance.set_result(event)
        if self.selected is not None and cycle.middle_repair and cycle.tokens[1].sequence == self.selected.sequence:
            choice = cycle.decisions[1]
            self.check((4, int(Kind.INDIRECT), self.program.a + 0x200),
                (choice.branch.position, int(choice.branch.kind), choice.branch.target),
                'same original direction repair first enters the wrong indirect successor')
            self.middle = dict(tick=tick, owner=self.selected.sequence, target=choice.branch.target)
        token = cycle.metadata
        if token is not None and self.selected is not None and token.sequence == self.selected.sequence:
            choice = cycle.decisions[2]
            self.check(True, cycle.final_repair and token.middle_corrected and self.middle is not None,
                'one original must require both a direction repair and a later target repair')
            self.check((4, int(Kind.INDIRECT), self.program.a, 'indirect-history'),
                (choice.branch.position, int(choice.branch.kind), choice.branch.target, choice.source),
                'independent ITTAGE refines the original Main target')
            self.check(self.program.flowing, events.prediction_ready, 'declared held/flowing repair mode')
            wrong = cycle.tokens[0]
            self.check(True, wrong is not None and wrong.pc == self.program.a + 0x200,
                'wrong successor really exists before the target repair')
            for getter in (bank.snapshot, bank.short_snapshot, bank.tage_snapshot, bank.target_snapshot):
                try:
                    getter(wrong)
                except ValueError:
                    pass
                else:
                    self.check(False, True, 'cancelled target may not retain any source domain')
            restored = model.stages[0]
            expected = ((token.history.history << SHIFT) ^ path_contribution((token.pc // 8) * 8 + 4, self.program.a)) % (1 << WIDTH)
            self.check((self.program.a, expected), (restored.pc, restored.history.history),
                'restore from the original history and the final indirect edge')
            self.restored = restored
            self.repair = dict(owner=token.sequence, tick=tick, wrong_owner=wrong.sequence,
                wrong_history=wrong.history.history, restored_owner=restored.sequence, restored_history=expected)
        if self.applied is not None and self.repair is not None:
            teacher = self.offers.get(id(self.applied.feedback))
            if teacher is not None and teacher.sequence == self.repair['owner']:
                for table, index, before, after, role in bank.short.effects:
                    if table == 0 and role == 'allocate':
                        feedback = self.applied.feedback
                        identity = tag(feedback.pc, feedback.context, 0)
                        self.check((self.pc, 4, int(Kind.INDIRECT), True),
                            (feedback.pc, feedback.position, feedback.kind, feedback.taken),
                            'original indirect result teaches only its earlier conditional NT')
                        self.check(Entry(True, identity, 2, 3), resident(bank, (0, index)), 'exact original short identity')
                        self.pending = dict(owner=teacher.sequence, index=index, tag=identity, written_tick=tick)
        feedback = bank.last_short_events.feedback
        if feedback is not None and cycle.tokens[2] is not None:
            self.offers[id(feedback)] = cycle.tokens[2]
        if token is not None and self.restored is not None:
            if token.sequence == self.restored.sequence:
                self.check(True, token.history is self.restored.history, 'exact restored original, not later equal history')
                self.new_a = dict(owner=token.sequence, tick=tick)
            if token.pc == self.pc and self.confirmed is not None and self.new_b is None:
                value = provider(bank, token)
                expected = self.confirmed
                if value is not None and (value.table, value.index, value.tag) == (0, expected['index'], expected['tag']) and value.counter < 4:
                    self.check_consumer(token)
                    self.new_b = dict(owner=token.sequence, tick=tick, provider=asdict(value))

    def finish(self):
        self.check(PHASES, tuple(row['phase'] for row in self.inputs), 'all declared original feedbacks accepted')
        self.check(True, all(value is not None for value in (self.middle, self.repair, self.confirmed, self.new_a, self.new_b)),
            'both repairs, actual learning, restored original and new consumer must all close')
        self.check(None, self.pending, 'no expected-only learning evidence')
        self.check(True, self.repair['owner'] < self.new_a['owner'] < self.new_b['owner'], 'ordered but passively collected owners')
        for source, token, snapshots, metadata in self.saved.values():
            self.check(snapshots, self.snapshots(token), 'all six original domains immutable')
            self.check(metadata, source.meta, 'public original metadata immutable')
        self.facts = dict(inputs=self.inputs, middle=self.middle, repair=self.repair, confirmed=self.confirmed,
            new_a=self.new_a, new_b=self.new_b, source_domains=6, scope='original direction/target/recovery/learning lifetime; full feature verdict owned by pytest')


class Checks(_ObservedChecks):
    completion_rules = RULES

    def __init__(self, profile, *, coverage=None):
        super().__init__(profile)
        self.coverage = Coverage(profile) if coverage is None else coverage
        self.teacher = None
        self._learning_witness = None
        self._restored_witness = None
        self._consumer_witness = None

    def save(self, source):
        token = super().save(source)
        if self.selected is not None and token.sequence == self.selected.sequence:
            self.teacher = source
        return token

    def early_consumer(self, source):
        super().early_consumer(source)
        self.mark(RULES[0], source.meta_tick)

    def target_consumer(self, source):
        super().target_consumer(source)
        self.mark(RULES[1], source.meta_tick)

    def checked(self, tick, *candidates):
        before = dict(middle=self.middle, repair=self.repair, pending=self.pending,
            confirmed=self.confirmed, new_a=self.new_a, new_b=self.new_b)
        super().checked(tick, *candidates)
        if before['middle'] is None and self.middle is not None:
            self.mark(RULES[2], tick)
        if before['repair'] is None and self.repair is not None:
            for rule in RULES[3:6]:
                self.mark(rule, tick)
        if before['pending'] is None and self.pending is not None:
            self.mark(RULES[6], tick)
        if before['confirmed'] is None and self.confirmed is not None:
            value = self.confirmed
            self._learning_witness = tuple(value[k] for k in ('owner', 'index', 'tag', 'written_tick', 'confirmed_tick'))
            self.mark(RULES[7], tick)
        if before['new_a'] is None and self.new_a is not None:
            token = self.cycle.metadata
            self.check(True, self.pipeline.model.published.get(token.sequence) is token,
                'restored witness was actually published after comparison')
            self._restored_witness = (token, tick)
            self.mark(RULES[8], tick)
        if before['new_b'] is None and self.new_b is not None:
            token = self.cycle.metadata
            self.check(True, self.pipeline.model.published.get(token.sequence) is token,
                'learned direction witness was actually published after comparison')
            self._consumer_witness = (token, tick)
            self.mark(RULES[9], tick)
        elif before['new_b'] is not None:
            # A later equal-context lookup is not the already observed first
            # complete consumer. Preserve the identity across coroutine delivery.
            self.new_b = before['new_b']

    def _receipt_for(self, token):
        found = [(source, owner) for source, owner, _, _ in self.saved.values() if owner.sequence == token.sequence]
        self.check(1, len(found), 'one complete saved actual receipt for each required original')
        source, owner = found[0]
        self.check(True, owner is token and self.pipeline.source_token(source) is token,
            'receipt token is the exact immutable published original')
        return source

    def finish(self):
        self.check(False, self.closed, 'single atomic lifetime completion')
        self.check(True, all(value is not None for value in (self.seed, self.stable, self.target_control,
            self.teacher, self.selected, self.restored, self._learning_witness,
            self._restored_witness, self._consumer_witness)), 'preparation, original teacher and all three checked witnesses required')
        self.check(True, self.acceptance is not None and self.acceptance.done(), 'real S1 acceptance was delivered')
        self.check(True, self.middle is not None and self.repair is not None and self.confirmed is not None
            and self.new_a is not None and self.new_b is not None, 'all completion reports required')
        teacher = self.pipeline.source_token(self.teacher)
        self.check(True, teacher is self.pipeline.model.published.get(teacher.sequence)
            and teacher.history is self.selected.history and teacher.sequence == self.selected.sequence,
            'original S1, published S3 and actual teacher receipt have one owner')
        self.check((teacher.sequence,) * 3,
            (self.middle['owner'], self.repair['owner'], self.confirmed['owner']), 'both repairs and learning belong to that original')
        self.check(self.middle['tick'] + 2, self.repair['tick'], 'target repair follows the same original direction repair')
        self.check(True, self.confirmed['written_tick'] > self.repair['tick'], 'original teaching follows its final result')
        self.check(self.confirmed['written_tick'] + 2, self.confirmed['confirmed_tick'], 'exact next full actual-state confirmation')
        self.check(self._learning_witness,
            tuple(self.confirmed[k] for k in ('owner', 'index', 'tag', 'written_tick', 'confirmed_tick')),
            'reported learning is the one actually compared')
        restored, restored_tick = self._restored_witness
        consumer, consumer_tick = self._consumer_witness
        self.check((self.restored.sequence, self.repair['restored_owner'], self.restored.history.history),
            (restored.sequence, restored.sequence, self.repair['restored_history']), 'new original is the exact restored owner and history')
        self.check(True, restored.history is self.restored.history, 'restored receipt cannot substitute an equal checkpoint')
        self.check((restored.sequence, restored_tick), (self.new_a['owner'], self.new_a['tick']), 'reported restored witness unchanged')
        self.check((consumer.sequence, consumer_tick), (self.new_b['owner'], self.new_b['tick']), 'reported first consumer witness unchanged')
        self.check(True, self.confirmed['confirmed_tick'] <= restored_tick < consumer_tick, 'actual confirmation precedes the fresh consumer')
        self.check(self.new_b['provider'], asdict(provider(self.pipeline.model.sources, consumer)), 'consumer metadata remains its own original')
        self.check((self.confirmed['index'], self.confirmed['tag']),
            (self.new_b['provider']['index'], self.new_b['provider']['tag']), 'consumer reads the confirmed learned identity')
        self.check(True, self.new_b['provider']['table'] == 0 and self.new_b['provider']['counter'] < 4,
            'original short negative experience, not a longer-provider substitute')
        for token in (teacher, restored, consumer):
            self._receipt_for(token)
        self.check(True, len(self.inputs) == len(PHASES) and len({row['owner'] for row in self.inputs}) == len(PHASES),
            'each of nine real outcomes has its own published original')
        for source, token, _, _ in self.saved.values():
            self.check(True, self.pipeline.source_token(source) is token
                and self.pipeline.model.published.get(token.sequence) is token, 'saved originals cannot be replaced by equal copies')
        super().finish()
        self.mark(RULES[10], consumer_tick)
        self.mark(RULES[11], consumer_tick)
        self.check(set(RULES), self.reached_rules, 'every semantic obligation required for atomic closure')
        for rule in RULES:
            self.coverage.record('checked', rule, consumer_tick)
        self.coverage.finish()
        self.closed = True
        self.facts = dict(deepcopy(self.facts), checked_obligations=list(RULES), atomic_lifetime_closed=True)
