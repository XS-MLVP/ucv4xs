from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
"""Pure source programs and checker corruption tests; these give no DUT credit."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.bpu.checker.early_direction import live_values, fast_values
from suites.frontend.bpu.bpu.checker.early_short_protection import EarlyShortProtectionChecks
from suites.frontend.bpu.bpu.coverage.early_short_protection import EarlyShortProtectionCoverage
from suites.frontend.bpu.bpu.model.early_aging import allocation, require_recovery_window
from suites.frontend.bpu.bpu.model.early_opposition import provider, resident, ahead_owner, main_counter, steady_history
from suites.frontend.bpu.bpu.model.early_short_protection import EDGES, OLDER_PATHS, rules, original_identity
from suites.frontend.bpu.bpu.model.early_protection import guidance
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from tests.bpu.scoreboard.test_early_protection import Program as LongProgram
from tests.bpu.scoreboard.test_early_direction_checking import actual_live, actual_fast
from tests.framework.fakes import event as synthetic_event


def maintenance(short):
    learning = short.learning
    decision = None if learning is None else allocation(learning.feedback, learning.useful)
    tables = []
    for table in range(2):
        selected = learning is not None and any(source.hit and source.provider == table
            and (learning.residents[table] is None or learning.residents[table].position == source.position)
            for source, _ in short._outcomes(learning.feedback))
        alloc = decision is not None and decision.candidate == table
        tables.append(dict(age=int(short.low_tick == 128), allocate=int(alloc), update=int(selected and not alloc)))
    return dict(low=short.low_tick, fire=int(learning is not None),
                need=int(decision is not None and decision.wrong_position is not None),
                mask=0 if decision is None else decision.mask, tables=tuple(tables))


class Program(LongProgram):
    recovery_position = FALLBACK

    def make_checks(self, pc, tag_class):
        return EarlyShortProtectionChecks(EarlyShortProtectionCoverage(), self.mode, pc)

    def step(self, event=None, *, mutate=None):
        event = self.event if event is None else event
        if event.redirect is not None:
            require_recovery_window(self.model.history.taken_edges, event.redirect.source.taken_edges,
                                    capacity=532, history_bits=397, shift=2)
        cycle = self.model.evaluate(event); self.tick += 2
        self.checks.pipeline.current_event = synthetic_event(self.tick)
        observed = actual_live(self.model.sources, cycle.enabled[1])
        observed['maintenance'] = maintenance(self.model.sources.short)
        if mutate is not None:
            mutate(observed)
        self.checks.candidates(dict(observed=dict(early_direction=observed)), event, cycle,
                               self.model, 'synthetic', None)
        self.checks.reached(self.tick)
        expected, actual = live_values(self.model.sources, cycle.enabled[1], observed)
        self.checks.check(expected, actual, 'complete synthetic protection comparison')
        expected, actual = fast_values(self.model.sources, cycle, actual_fast(self.model.sources, cycle))
        self.checks.check(expected, actual, 'complete synthetic original guidance comparison')
        for token, stage, repair in ((cycle.tokens[1], 2, cycle.middle_repair),
                                     (cycle.tokens[2], 3, cycle.final_repair)):
            if token is not None and repair:
                self.corrections.setdefault(token.sequence, []).append((self.tick, stage))
        self.model.advance(event)
        self.checks.checked(self.tick)
        return cycle

    def restore_flow(self, source):
        self.quiet()
        self.step(replace(self.event, redirect=Redirect(source.token.history,
                            (self.pc//16)*16+self.recovery_position, self.pc, True)))
        self.step()

    def original_short(self, source, older=OLDER_PATHS[0], *, mutate=None, longer=False):
        self.enable(False)
        for position in older:
            self.recovery_position = position
            source = self.query(source)
        self.recovery_position = FALLBACK
        source = self.query(source)
        self.enable(True)
        return self.bounded_source(source, mutate=mutate, longer=longer)

    def bounded_source(self, source, *, mutate=None, longer=False, expect_taken=None,
                       recovery_position=FALLBACK, open_window=None):
        self.quiet()
        accepted = (self.checks.open_original(longer=longer, expect_taken=expect_taken)
                    if open_window is None else open_window())
        rows = []
        cycle = self.step(replace(self.event, redirect=Redirect(source.token.history, (self.pc//16)*16+recovery_position, self.pc, True)))
        for _ in range(64):
            if cycle.metadata is not None and cycle.metadata.pc == self.pc:
                rows.append(self.receipt(cycle.metadata))
            if accepted.done():
                break
            cycle = self.step()
        else:
            raise AssertionError('no original short source accepted')
        closed = replace(self.event, prediction_ready=False)
        for _ in range(64):
            cycle = self.step(closed, mutate=mutate)
            if cycle.metadata is not None and cycle.metadata.pc == self.pc:
                rows.append(self.receipt(cycle.metadata))
            if self.model.stages[1:] == (None, None) and not self.model.sources.main_pending() and self.checks.pending is None:
                break
        else:
            raise AssertionError('accepted original work did not drain')
        matches = [row for row in rows if row.token.sequence == self.checks.selected.sequence]
        assert len(matches) == 1
        # Receipt timestamps in the generic pure helper assume no repair;
        # associate explicitly to the independently captured original S1 tick.
        source = matches[0]
        source.prediction_tick = self.checks.selected_tick
        self.checks.window_receipt(source)
        return source

    def positive(self, source):
        checks = self.checks
        before = resident(self.model.sources, checks.identity.key), checks.ledger.protection
        source = self.steer(source, 3); self.enable(True)
        source = self.until(source, lambda token: main_counter(token) == 3 and steady_history(token, 2)
            and (owner := ahead_owner(self.model.sources, token)) is not None and owner[1] == 3)
        checks.preserved_other_history(source, before)
        return source

    def seed(self):
        source = self.strong()
        source = self.original_short(source)
        source = self.original_short(source)
        return source

    def complete(self):
        source = self.seed(); checks = self.checks
        if self.mode in ('upper-hold', 'upper-release'):
            for edge in ('approach-upper', 'reach-upper', 'upper-hold'):
                source = self.positive(source)
                source = self.steer(source, 0)
                source = self.original_short(source)
                assert edge in checks.confirmed
            if self.mode == 'upper-release':
                source = self.steer(source, 3)
                source = self.original_short(source, OLDER_PATHS[1])
                assert 'upper-release' in checks.confirmed
                source = self.steer(source, 0)
                source = self.original_short(source, OLDER_PATHS[2])
        else:
            source = self.positive(source)
            for path, edge in zip(OLDER_PATHS, ('reach-lower', 'lower-hold', 'lower-recover'), strict=True):
                if edge == 'lower-recover':
                    source = self.steer(source, 0)
                source = self.original_short(source, path)
                assert edge in checks.confirmed
        if self.mode != 'upper-hold':
            source = self.original_short(source, OLDER_PATHS[1], longer=True)
        source = self.original_short(source, OLDER_PATHS[-1])
        checks.fresh_consumer(source); self.quiet()
        return source


@pytest.mark.parametrize('mode', tuple(EDGES))
async def test_original_short_program_compares_every_strength_boundary_and_parallel_allocation(mode):
    program = Program(mode); source = program.complete(); checks = program.checks
    assert checks.identity == original_identity(program.pc)
    assert set(checks.confirmed) == {edge[0] for edge in EDGES[mode]}
    assert all(written+2 == actual for _, written, actual in checks.confirmed.values())
    assert provider(program.model.sources, source.token).table == 0
    assert checks.boundaries.groups['checked'].coverage == 0
    checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == pytest.approx(
        100*len(rules(mode))/sum(len(rules(m)) for m in EDGES))


@pytest.mark.parametrize('cell', ((0, 0), (1, 511)))
async def test_bad_actual_protection_cannot_advance_the_independent_short_ledger(cell):
    program = Program('upper-hold'); program.seed(); checks = program.checks
    before = program.model.sources.short.state(), checks.ledger.counter, checks.ledger.protection
    def corrupt(actual):
        rows = [list(row) for row in actual['useful']]
        rows[cell[0]][cell[1]] ^= 1
        actual['useful'] = tuple(tuple(row) for row in rows)
    with pytest.raises(AssertionError):
        program.step(replace(program.event, prediction_ready=False), mutate=corrupt)
    assert (program.model.sources.short.state(), checks.ledger.counter, checks.ledger.protection) == before
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('mask', 'short-update', 'long-allocate'))
async def test_parallel_command_corruption_is_not_hidden_by_correct_short_prediction(fault):
    program = Program('lower-recover'); source = program.seed()
    source = program.positive(source); corrupted = []
    def corrupt(actual):
        learning = program.model.sources.short.learning
        if learning is None or guidance(learning.feedback, program.checks.identity) != (True, 'penalty'):
            return
        control = actual['maintenance']; corrupted.append(program.tick)
        if fault == 'mask':
            control['mask'] ^= 2
        else:
            table, field = (0, 'update') if fault == 'short-update' else (1, 'allocate')
            control['tables'][table][field] ^= 1
    with pytest.raises(AssertionError):
        program.original_short(source, OLDER_PATHS[1], mutate=corrupt)
    assert len(corrupted) == 1 and not program.checks.parallel_confirmed
    assert program.checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-long-consumer', 'missing-seed', 'unconfirmed-parallel'))
async def test_incomplete_short_proof_never_grants_checked_credit(fault):
    program = Program('lower-recover'); program.complete(); checks = program.checks
    if fault == 'missing-long-consumer':
        checks.completed.discard('fresh-long-consumer')
    elif fault == 'missing-seed':
        checks.seeded = False
    else:
        checks.parallel_pending = ('not-yet-compared',)
    with pytest.raises(AssertionError):
        checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('wrong-source', 'wrong-acceptance-tick'))
async def test_equal_pc_is_not_enough_to_associate_a_bounded_source(fault):
    program = Program('upper-hold'); source = program.seed(); checks = program.checks
    if fault == 'wrong-source':
        source = checks.strong
    else:
        source.prediction_tick -= 2
    with pytest.raises(AssertionError):
        checks.window_receipt(source)
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_leaving_ready_open_for_a_younger_source_invalidates_the_boundary_program():
    program = Program('lower-recover'); source = program.seed()
    step = program.step; deliberately_open = []
    def delayed_close(event=None, **kwargs):
        checks = program.checks
        if event is not None and checks.window_active and checks.selected is not None:
            event = replace(event, prediction_ready=True)
            deliberately_open.append(program.tick)
        return step(event, **kwargs)
    program.step = delayed_close
    with pytest.raises(AssertionError, match='younger S1 acceptance'):
        program.original_short(source)
    assert deliberately_open and program.checks.boundaries.groups['checked'].coverage == 0


async def test_new_issue_scope_cannot_discard_an_undelivered_accepted_source():
    program = Program('upper-hold'); source = program.seed(); checks = program.checks
    # A completed S1 future is not by itself a completed S3 delivery scope.
    checks.window_active = True
    with pytest.raises(AssertionError, match='S3 receipt delivery'):
        checks.open_original()
    assert checks.boundaries.groups['checked'].coverage == 0
