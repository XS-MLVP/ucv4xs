"""Pure conditional execution-prefix program, independent of hardware sampling."""
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from bpuverify.bpu.model.conditional_prefix import PROFILES, target_state
from bpuverify.bpu.model.pipeline import Outcome, Resolution, Redirect
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.path_history import SHIFT, WIDTH, path_contribution
from bpuverify.tage.model.semantic import TABLES, HISTORIES
from tests.bpu.scoreboard._indirect_path_program import Program as OriginalProgram


class Program(OriginalProgram):
    def __init__(self, profile, *, sources_factory=None):
        entry, self.direction, mode = profile.split('.')
        self.profile = profile
        super().__init__(0x40000001 if entry == 'compressed-entry' else 0x40000002, flowing=mode == 'flowing', sources_factory=sources_factory)
        self.condition_target = self.a + 0x100
        self.conditional_feedbacks = []
        self.guard_state = None
        self.guard_cycles = 0
        self.prefix_selected = None
        self.prefix_repairs = []
        self.return_discovered = False

    def restart(self):
        self.quiet()
        source = self.anchor
        require_recovery_window(self.model.history.taken_edges, source.history.taken_edges,
            capacity=WIDTH, history_bits=max(HISTORIES), shift=SHIFT)
        # Match the existing RecoveryDriver contract: release ready and assert
        # the normal redirect together. Waiting for pulse cleanup first discards
        # the original ahead read ancestry and tests a different experiment.
        self.step(replace(self.event, redirect=Redirect(source.history,
            (self.a // 8) * 8 + 4, self.pc, True)))

    def step(self, event=None):
        event = self.event if event is None else event
        cycle = super().step(event)
        if self.guard_state is not None:
            assert target_state(self.model.sources) == self.guard_state, 'unexecuted indirect changed learned target state'
            self.guard_cycles += 1
        if self.prefix_selected is not None:
            for token, decision, repaired in ((cycle.tokens[1], cycle.decisions[1], cycle.middle_repair),
                    (cycle.tokens[2], cycle.decisions[2], cycle.final_repair)):
                if token is not None and token.sequence == self.prefix_selected.sequence and repaired:
                    expected = ((token.history.history << SHIFT) ^ path_contribution(
                        (token.pc // 8) * 8 + decision.branch.position, decision.branch.target)) % (1 << WIDTH)
                    assert self.model.history.history == expected
                    self.prefix_repairs.append(dict(owner=token.sequence, tick=self.tick,
                        position=decision.branch.position, target=decision.branch.target))
        return cycle

    def configure(self, *, early=None, tage=None, target=None):
        self.quiet()
        enabled = list(self.event.enabled)
        if early is not None:
            enabled[1] = early
        if tage is not None:
            enabled[3] = tage
        if target is not None:
            enabled[5] = target
        self.event = replace(self.event, enabled=tuple(enabled))
        for _ in range(8):
            self.step(replace(self.event, prediction_ready=False))
            if self.model.control_pipe[-1] == self.event.enabled:
                break
        else:
            raise AssertionError('declared controls were not applied')
        self.quiet()

    def resolve(self, source, position, taken, *, wrong, room=False, kind=None, target=None):
        idle = self.quiet()
        target = (self.condition_target if position == 2 else self.pc if source.pc == self.a else self.a) if target is None else target
        kind = (Kind.CONDITIONAL if position == 2 else Kind.DIRECT) if kind is None else kind
        request = Resolution(source.history, source.pc,
            (Outcome(position, target, kind, taken, mispredict=wrong),), origin=source)
        if room:
            feedback = self.model.sources.feedback_for(request)
            for _ in range(128):
                candidate = self.model.sources.tage.allocation_at_next_accept(feedback)
                if candidate is not None and candidate[0] == TABLES - 1:
                    break
                self.step(idle)
            else:
                raise AssertionError('maximum-history negative source was not admitted within semantic budget')
        self.step(replace(idle, feedback=request))
        self.feedbacks.append(request)
        self.quiet()
        if source.pc == self.pc and position == 2 and taken and not self.return_discovered:
            # A fixed conditional immediate cannot be changed by later same-kind
            # Main feedback. Its distinct D target is part of the program from
            # first discovery. Discover the real D4->A return before warming it.
            self.return_discovered = True
            self.restart()
            successor = self.source(pc=self.condition_target)
            self.resolve(successor, 4, True, wrong=True, kind=Kind.DIRECT, target=self.a)

    def conditional(self, source, *, taken=True, wrong=True, executed_indirect=False, maximum_allocation=False,
            indirect_target=None, indirect_wrong=False):
        idle = self.quiet()
        outcomes = (Outcome(2, self.condition_target, Kind.CONDITIONAL, taken, mispredict=wrong),)
        if executed_indirect:
            assert not taken
            outcomes += (Outcome(4, self.a if indirect_target is None else indirect_target, Kind.INDIRECT,
                True, mispredict=indirect_wrong),)
        request = Resolution(source.history, source.pc, outcomes, origin=source)
        enabled = self.model.control_pipe[-1][5]
        offered = self.model.sources.targets.feedback_for(request) if enabled else None
        assert (offered is not None) == (executed_indirect and enabled), 'learning belongs to the actually executed enabled prefix'
        if maximum_allocation:
            feedback = self.model.sources.feedback_for(request)
            for _ in range(128):
                candidate = self.model.sources.tage.allocation_at_next_accept(feedback)
                if candidate is not None and candidate[0] == TABLES - 1:
                    break
                self.step(idle)
            else:
                raise AssertionError('current-history maximum provider was not admitted')
        self.step(replace(idle, feedback=request))
        self.conditional_feedbacks.append(request)
        self.quiet()

    def wanted(self, token):
        branches, fields, late = self.model.sources.tage_decision(token)
        slot = next(i for i, branch in enumerate(branches) if branch is not None and branch.position == 2)
        return branches, fields, late, slot

    def direction_ready(self, token):
        _, fields, late, slot = self.wanted(token)
        return (fields.get(f'{slot}.has_provider') and fields.get(f'{slot}.counter') == (3 if self.direction == 'weak-alternate' else 5)
            and fields.get(f'{slot}.table') == TABLES - 1 and not fields.get(f'{slot}.has_alt')
            and fields.get(f'{slot}.use_provider') == (self.direction == 'strong-provider')
            and (bool(fields.get(f'{slot}.taken')) if self.direction == 'strong-provider'
                else not fields.get(f'{slot}.valid') and bool(fields.get(f'{slot}.alternative')))
            and late.branch.position == 2
            and late.branch.target == self.condition_target)

    def prepare_sources(self):
        # Four fixed instructions: A4->B, B2->D, B4->A (indirect), D4->A.
        # Direction is dynamic; the conditional immediate is never rewritten.
        self.anchor = self.source(pc=self.a)
        self.resolve(self.anchor, 4, True, wrong=True)
        self.resolve(self.query(), 4, True, wrong=True, kind=Kind.INDIRECT)
        self.resolve(self.query(), 2, True, wrong=True)
        self.seed = self.warm()
        edge = (path_contribution((self.a // 8) * 8 + 4, self.pc) << (2 * SHIFT)) ^ (
            path_contribution((self.pc // 8) * 8 + 2, self.condition_target) << SHIFT) ^ path_contribution(
                (self.condition_target // 8) * 8 + 4, self.a)
        recent = 0
        for bit in range(0, max(HISTORIES), 3 * SHIFT):
            recent ^= edge << bit
        recent %= 1 << max(HISTORIES)
        self.anchor = self.source(lambda t: t.history.history % (1 << max(HISTORIES)) == recent, pc=self.a)
        self.configure(early=False, tage=False, target=False)
        # A real wrong target must create the first indirect experience. First
        # weaken Main's condition, then learn C while ITTAGE is disabled. The
        # conditional is already predicted NT when the indirect reports a
        # wrong target; two branch errors are not invented in one prefix.
        for _ in range(2):
            source = self.query()
            late = self.model.sources.target_snapshot(source, resolved=True).late
            self.conditional(source, taken=False, wrong=late.branch.kind == Kind.CONDITIONAL,
                executed_indirect=True)
        self.conditional(self.query(), taken=False, wrong=False, executed_indirect=True,
            indirect_target=self.a + 0x200, indirect_wrong=True)
        self.configure(target=True)
        for number in range(3):
            self.conditional(self.query(), taken=False, wrong=False, executed_indirect=True,
                indirect_wrong=number == 0)
        original = self.query()
        prediction = self.model.sources.target_snapshot(original, resolved=True).prediction
        assert prediction.provider is not None and prediction.target // 2 == self.a and prediction.confidence == 3
        # Retain target A independently while Main's selected indirect learns
        # a distinct C. Then restore taken base direction, using actual first
        # conditional mispredictions, before allocating the negative provider.
        self.configure(target=False)
        self.conditional(self.query(), taken=False, wrong=False, executed_indirect=True,
            indirect_target=self.a + 0x200, indirect_wrong=True)
        self.configure(target=True)
        for _ in range(2):
            self.conditional(self.query(), wrong=True)
        self.configure(tage=True)
        self.conditional(self.query(), taken=False, wrong=True, executed_indirect=True, maximum_allocation=True)
        self.conditional(self.query(), taken=False, wrong=False, executed_indirect=True)
        self.configure(tage=False)
        return dict(stable_predecessor=self.anchor.sequence, target_original=original.sequence,
            real_feedbacks=len(self.feedbacks), fixed_conditional_target=self.condition_target)

    def complete(self):
        initial = self.prepare_sources()
        self.conditional(self.query())  # Main NT0 -> NT1; TAGE remains strong NT2.
        self.configure(tage=True)
        count = 1 if self.direction == 'weak-alternate' else 3
        for number in range(count):
            source = self.query()
            self.conditional(source, wrong=number == 0)
        self.configure(early=True)
        self.restart()
        bank = self.model.sources
        self.guard_state = target_state(bank)
        winner = None
        for _ in range(256):
            cycle = self.model.evaluate(self.event)
            first = cycle.tokens[0]
            if (self.prefix_selected is None and first is not None and first.pc == self.pc
                    and cycle.fires[1] and not cycle.flushes[0]
                    and cycle.decisions[0].source in ('ahead', 'ahead-direction')
                    and cycle.decisions[0].branch.position == 2
                    and cycle.decisions[0].branch.target == self.condition_target and self.direction_ready(first)):
                values = bank.current_short(True).values()
                if any(values.get(f'{w}.valid') and values.get(f'{w}.position') == 2 for w in range(4)):
                    self.prefix_selected = first
            if cycle.metadata is not None and self.prefix_selected is not None and cycle.metadata.sequence == self.prefix_selected.sequence:
                cycle = self.step(self.event if self.flowing else replace(self.event, prediction_ready=False))
                winner = cycle.metadata
                target = bank.target_snapshot(winner, resolved=True)
                assert target.prediction is not None and target.prediction.provider is not None
                assert target.prediction.target // 2 == self.a and target.prediction.confidence == 3
                final = cycle.decisions[2]
                assert (final.branch.position, final.branch.kind, final.branch.target) == (2, Kind.CONDITIONAL, self.condition_target)
                assert final.source != 'indirect-history'
                if self.direction == 'weak-alternate':
                    assert cycle.final_repair and winner.middle_corrected and winner.middle.branch.kind == Kind.INDIRECT
                else:
                    assert not cycle.final_repair and not winner.middle_corrected
                break
            self.step()
        assert winner is not None, 'qualified independent conditional never won the original target selection'
        self.quiet()
        snapshots = (bank.snapshot(winner), bank.short_snapshot(winner), bank.tage_snapshot(winner),
            bank.tage_snapshot(winner, resolved=True), bank.target_snapshot(winner), bank.target_snapshot(winner, resolved=True))
        frozen_target = deepcopy(bank.defined_ittage_metadata(winner))
        self.conditional(winner, wrong=False)
        preserved = target_state(bank)
        assert preserved == self.guard_state and self.guard_cycles > 0
        guarded = self.guard_cycles
        self.guard_state = None
        # A later actually executed NT/indirect prefix may legitimately train
        # the indirect predictor. Stop on the actual semantic NT consumer,
        # within the counter capacity, instead of a guessed wait/count.
        for _ in range(8):
            source = self.query()
            late = bank.target_snapshot(source, resolved=True).late
            if late.branch.kind == Kind.INDIRECT:
                fresh = source
                break
            self.conditional(source, taken=False, wrong=late.branch.kind == Kind.CONDITIONAL, executed_indirect=True)
        else:
            raise AssertionError('legal NT feedback did not reach an indirect consumer within counter capacity')
        final = bank.target_snapshot(fresh, resolved=True)
        assert (final.late.branch.position, final.late.branch.kind, final.late.branch.target, final.late.source) == (4, Kind.INDIRECT, self.a, 'indirect-history')
        assert final.prediction.provider is not None and final.prediction.target // 2 == self.a
        assert final.prediction.confidence == 3
        assert bank.defined_ittage_metadata(winner) == frozen_target
        assert (bank.snapshot(winner), bank.short_snapshot(winner), bank.tage_snapshot(winner),
            bank.tage_snapshot(winner, resolved=True), bank.target_snapshot(winner), bank.target_snapshot(winner, resolved=True)) == snapshots
        return dict(profile=self.profile, initial=initial, winner=winner.sequence,
            early=asdict(winner.early), middle=asdict(winner.middle), final=asdict(bank.target_snapshot(winner, resolved=True).late),
            original_target_metadata=frozen_target, repairs=self.prefix_repairs, guard_cycles=guarded,
            no_indirect_feedback_in_conditional_only_prefix=True, learned_target_state_unchanged=True,
            fresh_indirect_consumer=dict(owner=fresh.sequence, target=final.late.branch.target, confidence=final.prediction.confidence),
            additional_real_feedbacks=len(self.conditional_feedbacks), six_original_domains_immutable=True,
            target_state_sha256=sha256(repr(preserved).encode()).hexdigest())
