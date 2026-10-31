"""Compare independent original ownership and actual exclusion of younger learning."""
import asyncio
from copy import deepcopy
from dataclasses import asdict
from toffee import XEvent, XPhase
from suites.frontend.bpu.bpu.checker.early_direction_learning import EarlyDirectionChecks
from suites.frontend.bpu.bpu.coverage.conditional_prefix import Coverage
from suites.frontend.bpu.bpu.model.conditional_prefix import PROFILES, RULES, Layout, target_state
from suites.frontend.bpu.bpu.model.path_history import SHIFT, WIDTH, path_contribution
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.tage.model.semantic import TABLES, HISTORIES


class _ObservedChecks(EarlyDirectionChecks):
    def __init__(self, profile):
        if profile not in PROFILES: raise ValueError('declared semantic profile required')
        self.program = Layout(profile)
        super().__init__(None, self.program.b)
        self.pending = None
        self.saved, self.plans, self.accepted_inputs = {}, {}, []
        self.redirect_count, self.last_redirect = 0, None
        self.seed = self.stable = self.target_control = None
        self.acceptance = self.candidate = self.selected = self.selected_tick = None
        self.middle = self.winner = self.final = None
        self.guard = None
        self.guard_cycles = self.actual_guard_cycles = self.actual_read_cycles = 0
        self.actual_ticks = []
        self.conditional_acceptance = None
        self.fresh = None

    @property
    def bank(self): return self.pipeline.model.sources

    def snapshots(self, token):
        b = self.bank
        return (b.snapshot(token), b.short_snapshot(token), b.tage_snapshot(token),
            b.tage_snapshot(token, resolved=True), b.target_snapshot(token), b.target_snapshot(token, resolved=True))

    def save(self, source):
        token = self.pipeline.source_token(source)
        self.check(True, self.pipeline.model.published.get(token.sequence) is token, 'exact published original')
        self.saved.setdefault(source.meta_tick, (source, token, self.snapshots(token), deepcopy(source.meta)))
        return token

    def ready(self, token):
        branches, fields, late = self.bank.tage_decision(token)
        slot = next((i for i, branch in enumerate(branches) if branch is not None and branch.position == 2), None)
        if slot is None: return False
        p = self.program
        return (fields.get(f'{slot}.has_provider') and fields.get(f'{slot}.counter') == (5 if p.strong else 3)
            and fields.get(f'{slot}.table') == TABLES - 1 and not fields.get(f'{slot}.has_alt')
            and fields.get(f'{slot}.use_provider') == p.strong
            and (bool(fields.get(f'{slot}.taken')) if p.strong else
                not fields.get(f'{slot}.valid') and bool(fields.get(f'{slot}.alternative')))
            and late.branch.position == 2 and late.branch.target == p.d)

    def plan(self, name, source, outcomes):
        token = self.save(source)
        self.check(False, token.sequence in self.plans, 'feedback cannot reuse the same original')
        self.plans[token.sequence] = (name, source, tuple(outcomes))

    def open(self):
        self.check(True, all(v is not None for v in (self.seed, self.stable, self.target_control)),
            'actual early source, stable path, and retained target required')
        self.check(False, self.bank.main_pending(), 'no indirect or base work may leak into guard')
        self.guard = target_state(self.bank)
        self.acceptance = asyncio.get_running_loop().create_future()
        return self.acceptance

    def candidates(self, row, events, cycle, model, phase, previous):
        self.events, self.cycle, self.candidate = events, cycle, None
        self.last_observed = row['observed']
        first = cycle.tokens[0]
        if self.acceptance is not None and not self.acceptance.done() and first is not None:
            choice = cycle.decisions[0]
            if (first.pc == self.pc and cycle.fires[1] and not cycle.flushes[0]
                    and choice.source in ('ahead', 'ahead-direction') and choice.branch.position == 2
                    and choice.branch.target == self.program.d and self.ready(first)):
                values = model.sources.current_short(True).values()
                if any(values.get(f'{w}.valid') and values.get(f'{w}.position') == 2 for w in range(4)):
                    self.candidate = first
        return ()

    def failure_evidence(self):
        """One first-failure snapshot, not an exported per-cycle trace."""
        frame = self.bank.ahead.frame
        actual = getattr(self, 'last_observed', {})
        return dict(last_tick=self.pipeline.last_tick, original_count=len(self.saved),
            accepted_inputs=self.accepted_inputs, guard_open=self.guard is not None,
            reference_ahead_frame=None if frame is None else asdict(frame),
            actual_ahead=actual.get('ahead'), actual_early_direction=actual.get('early_direction'),
            latest_reference_ahead_event=None if self.bank.last_ahead_events is None else asdict(self.bank.last_ahead_events),
            reference_pending=[[asdict(v) for v in pending.versions.values()] for pending in self.bank.ahead.pending])

    def reached(self, tick, *args): pass

    def checked(self, tick, *args):
        events, cycle = self.events, self.cycle
        if events.redirect is not None:
            self.redirect_count += 1
            self.last_redirect = (tick, events.redirect.source, events.prediction_ready)
        if events.feedback is not None:
            request = events.feedback
            self.check(True, request.origin.sequence in self.plans, 'only a predeclared original trains')
            name, source, expected = self.plans[request.origin.sequence]
            self.check(True, self.pipeline.source_token(source) is request.origin, 'actual acceptance owns exact source')
            active = tuple(branch for branch in request.branches if branch is not None)
            self.check(expected, active, 'complete execution prefix accepted unchanged')
            self.accepted_inputs.append(dict(name=name, owner=request.origin.sequence, tick=tick,
                outcomes=[asdict(branch) for branch in active]))
            if name == 'guarded-conditional-only':
                self.check((2,), tuple(branch.position for branch in active), 'unexecuted indirect absent from resolved prefix')
                self.check(None, self.bank.targets.feedback_for(request), 'conditional-only outcome cannot train indirect')
                self.conditional_acceptance = tick
        if self.guard is not None:
            self.check(self.guard, target_state(self.bank), 'all learned target state unchanged during conditional-only prefix')
            self.guard_cycles += 1
        if self.candidate is not None:
            event = self.pipeline.current_event
            self.check(True, isinstance(event, XEvent) and event.phase is XPhase.RISING_STABLE and event.tick == tick,
                'release only from an already compared actual S1 event')
            self.selected, self.selected_tick = self.candidate, tick
            self.acceptance.set_result(event)
        if self.selected is not None and cycle.tokens[1] is not None and cycle.tokens[1].sequence == self.selected.sequence:
            choice = cycle.decisions[1]
            self.middle = dict(owner=self.selected.sequence, tick=tick, repair=cycle.middle_repair,
                position=choice.branch.position, target=choice.branch.target)
            self.check(not self.program.strong, cycle.middle_repair, 'direction repair iff weak provider follows taken base')
            self.check(self.program.d if self.program.strong else self.program.c, choice.branch.target,
                'independent middle target, not the indirect-history hit')
        token = cycle.metadata
        if token is not None and self.selected is not None and token.sequence == self.selected.sequence:
            prediction = self.bank.target_snapshot(token, resolved=True).prediction
            self.check(True, prediction is not None and prediction.provider is not None, 'unused indirect provider really hits')
            self.check((self.program.a, 3), (prediction.target // 2, prediction.confidence), 'retained wrong-path target experience')
            choice = cycle.decisions[2]
            self.check((2, Kind.CONDITIONAL, self.program.d),
                (choice.branch.position, choice.branch.kind, choice.branch.target), 'earlier taken condition owns final full target')
            self.check(False, choice.source == 'indirect-history', 'unused indirect hit cannot select target')
            self.check(not self.program.strong, cycle.final_repair, 'target repair iff the middle chose a wrong indirect')
            self.check(self.program.flowing, events.prediction_ready, 'declared held or flowing final decision')
            self.check(True, self.middle is not None, 'selected original middle decision observed')
            if cycle.final_repair:
                expected = ((token.history.history << SHIFT) ^ path_contribution(
                    (token.pc // 8) * 8 + 2, self.program.d)) % (1 << WIDTH)
                self.check(expected, self.pipeline.model.history.history, 'final conditional edge restores original history')
            self.winner = token
            self.final = dict(owner=token.sequence, tick=tick, repair=cycle.final_repair,
                target=choice.branch.target, position=choice.branch.position, indirect_provider=prediction.provider,
                indirect_target=prediction.target // 2, indirect_confidence=prediction.confidence)

    def actual(self, event, value):
        if self.guard is None: return
        self.check(True, event.phase is XPhase.RISING_STABLE, 'auxiliary sampler is an actual stable monitor event')
        self.check(0, value['reset'], 'guard is outside initialization')
        self.check(0, value['region_write'], 'unexecuted indirect cannot allocate or touch region directory')
        self.check((0,) * 3, tuple(value['updates']), 'no offered target-table update for unexecuted indirect')
        self.check((0,) * 6, tuple(value['incoming']), 'no actual indirect write-buffer insertion')
        self.check((0,) * 6, tuple(value['maintenance']), 'no aging sweep masks a missing target comparison')
        self.check((0,) * 6, tuple(int(v and r) for v, r in zip(value['write_valid'], value['write_ready'], strict=True)),
            'no actual indirect SRAM service during conditional-only guard')
        expected = tuple((int(region is not None), region) for region in self.bank.indirect.regions.regions)
        observed = tuple((slot['valid'], slot['region'] if slot['valid'] else None) for slot in value['regions'])
        self.check(expected, observed, 'actual complete region directory matches retained semantic state')
        self.actual_guard_cycles += 1
        self.actual_read_cycles += int(any(value['reads']))
        self.actual_ticks.append(event.tick)

    def close_guard(self):
        self.check(True, self.conditional_acceptance is not None, 'actual conditional-only feedback must be accepted')
        self.check(True, self.actual_guard_cycles > 0 and self.actual_read_cycles > 0,
            'actual indirect reads allowed, but no target learning')
        self.check(True, min(self.actual_ticks) <= self.conditional_acceptance < max(self.actual_ticks),
            'write-free actual window surrounds accepted conditional-only feedback')
        self.check(self.guard_cycles, self.actual_guard_cycles, 'every guarded comparison has an auxiliary actual sample')
        self.guard = None

    def finish(self, fresh):
        token = self.save(fresh)
        value = self.bank.target_snapshot(token, resolved=True)
        self.check((4, Kind.INDIRECT, self.program.a, 'indirect-history'),
            (value.late.branch.position, value.late.branch.kind, value.late.branch.target, value.late.source),
            'fresh legally executed indirect consumes retained target')
        self.check(True, value.prediction.provider is not None, 'fresh indirect has an independent learned provider')
        self.check((self.program.a, 3), (value.prediction.target // 2, value.prediction.confidence), 'fresh target and confidence retained')
        self.check(len(self.plans), len(self.accepted_inputs), 'all and only planned real feedback accepted')
        self.check(True, self.winner is not None and self.guard is None, 'selected original and actual no-write window closed')
        self.check(3, len({self.program.a, self.program.c, self.program.d}), 'all targets must be independently distinguishable')
        for source, original, snapshots, metadata in self.saved.values():
            self.check(snapshots, self.snapshots(original), 'all six original domains remain immutable')
            self.check(metadata, source.meta, 'all public original metadata remain immutable')
        return dict(profile=self.program.profile, status='PASS', middle=self.middle, final=self.final,
            feedbacks=self.accepted_inputs, guard_cycles=self.guard_cycles,
            actual_guard_cycles=self.actual_guard_cycles, actual_read_cycles=self.actual_read_cycles,
            conditional_acceptance=self.conditional_acceptance, fresh=dict(owner=token.sequence, tick=fresh.meta_tick,
                target=value.late.branch.target, confidence=value.prediction.confidence),
            saved_originals=len(self.saved), source_domains=6, six_original_domains_immutable=True,
            actual_unexecuted_indirect_updates=0, actual_unexecuted_indirect_writes=0,
            production_promotion=False, formal_functional_point_credit=False)


class Checks(_ObservedChecks):
    completion_rules = RULES

    def __init__(self, profile, *, coverage=None):
        super().__init__(profile)
        self.coverage = Coverage(profile) if coverage is None else coverage
        self._middle_witness = self._final_witness = self._guard_witness = None
        self.teacher = None

    def save(self, source):
        token = super().save(source)
        if self.winner is not None and token is self.winner: self.teacher = source
        return token

    def open(self):
        p = self.program
        for source in (self.seed, self.stable, self.target_control): self.check(True, source is not None, 'all preparation receipts required')
        token = self.pipeline.source_token(self.seed)
        self.check((p.b, 2, Kind.CONDITIONAL, p.d),
            (token.pc, token.early.branch.position, token.early.branch.kind, token.early.branch.target), 'own early conditional immediate')
        self.mark(RULES[0], self.seed.meta_tick)
        token = self.pipeline.source_token(self.stable)
        self.check((p.a, p.recent), (token.pc, token.history.history % (1 << max(HISTORIES))), 'real stable executed path')
        self.mark(RULES[1], self.stable.meta_tick)
        token = self.pipeline.source_token(self.target_control)
        prediction = self.bank.target_snapshot(token, resolved=True).prediction
        self.check(True, prediction is not None and prediction.provider is not None, 'real original indirect target hit')
        self.check((p.a, 3), (prediction.target // 2, prediction.confidence), 'independently learned target before guarded prefix')
        self.mark(RULES[2], self.target_control.meta_tick)
        return super().open()

    def checked(self, tick, *args):
        old_middle, old_final = self.middle, self.final
        super().checked(tick, *args)
        if old_middle is None and self.middle is not None:
            self._middle_witness = deepcopy(self.middle)
            self.mark(RULES[3], tick)
        if old_final is None and self.final is not None:
            self._final_witness = (self.winner, deepcopy(self.final))
            self.mark(RULES[4], tick)
            self.mark(RULES[5], tick)
        if self.events.feedback is not None and self.conditional_acceptance == tick:
            self.mark(RULES[6], tick)

    def close_guard(self):
        super().close_guard()
        self._guard_witness = (self.conditional_acceptance, self.guard_cycles,
            self.actual_guard_cycles, self.actual_read_cycles, tuple(self.actual_ticks))
        for rule in RULES[7:10]: self.mark(rule, self.actual_ticks[-1])

    def _receipt(self, source):
        token = self.pipeline.source_token(source)
        saved = self.saved.get(source.meta_tick)
        self.check(True, saved is not None and saved[0] is source and saved[1] is token
            and self.pipeline.model.published.get(token.sequence) is token, 'exact saved complete original, never an equal copy')
        return token

    def finish(self, fresh):
        self.check(False, self.closed, 'single atomic semantic closure')
        self.check(True, all(v is not None for v in (self.teacher, self.selected, self.winner,
            self._middle_witness, self._final_witness, self._guard_witness)), 'all actual selection and no-learning witnesses required')
        self.check(True, self.acceptance is not None and self.acceptance.done(), 'actual original S1 release delivered')
        teacher = self._receipt(self.teacher)
        self.check(True, teacher is self.winner and teacher.sequence == self.selected.sequence
            and teacher.history is self.selected.history, 'one exact original from accepted S1 to published S3')
        token, final = self._final_witness
        self.check(True, token is teacher, 'final comparison witness owns the teacher')
        self.check(final, self.final, 'final decision report remains the one actually compared')
        self.check(self._middle_witness, self.middle, 'middle decision report remains the one actually compared')
        self.check((teacher.sequence, self.middle['tick'] + 2),
            (self.middle['owner'], self.final['tick']), 'middle and final are adjacent observations of the same original')
        current_guard = (self.conditional_acceptance, self.guard_cycles,
            self.actual_guard_cycles, self.actual_read_cycles, tuple(self.actual_ticks))
        self.check(self._guard_witness, current_guard, 'reported no-learning window is the actual compared window')
        self.check(True, self.conditional_acceptance > self.final['tick'], 'actual feedback follows original final decision')
        self.check(True, fresh.meta_tick > self.actual_ticks[-1], 'fresh indirect follows the complete no-learning window')
        self.check(True, len(self.accepted_inputs) == len({row['owner'] for row in self.accepted_inputs}),
            'every real feedback uses a distinct actual original')
        for source, _, _, _ in self.saved.values(): self._receipt(source)
        result = super().finish(fresh)
        self.mark(RULES[10], fresh.meta_tick)
        self.mark(RULES[11], fresh.meta_tick)
        self.check(set(RULES), self.reached_rules, 'all human semantic requirements must close together')
        for rule in RULES: self.coverage.record('checked', rule, fresh.meta_tick)
        self.coverage.finish()
        self.closed = True
        return dict(result, atomic_lifetime_closed=True, checked_obligations=list(RULES))
