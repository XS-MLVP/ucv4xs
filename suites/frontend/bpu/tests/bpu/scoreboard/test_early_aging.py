"""Independent event counts, real reset-derived program and negative checker boundaries."""
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest

from suites.frontend.bpu.bpu.checker.early_aging import EarlyAgingChecks, all_protection
from suites.frontend.bpu.bpu.coverage.early_aging import EarlyAgingCoverage, AGE_RULES
from suites.frontend.bpu.bpu.model.early_aging import FailureLedger, allocation, aged, require_recovery_window
from suites.frontend.bpu.bpu.model.early_opposition import provider, main_counter, steady_history, FALLBACK
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.utage.model.semantic import Feedback, Context, Source
from tests.bpu.scoreboard.test_early_opposition import Program as SourceProgram
from tests.bpu.scoreboard.test_early_positive import Program as PositiveProgram
from tests.bpu.scoreboard.test_early_direction_checking import actual_live, actual_fast
from suites.frontend.bpu.bpu.checker.early_direction import live_values, fast_values


def feedback(*, hit=True, table=1, predicted=False, base=False, position=2, end=2, kind=1,
             valid=True, taken=True):
    return Feedback(0x40000000, Context(), (0, 322),
        (Source(valid, position, hit, table, 3, predicted, base),), end, taken, kind)


@pytest.mark.parametrize('table,protection,expected', (
    (1, (0, 0), (None, True)), (1, (3, 3), (None, True)),
    (0, (3, 0), (1, False)), (0, (0, 1), (None, True))))
def test_failure_depends_on_original_provider_and_longer_protection_not_counter(table, protection, expected):
    result = allocation(feedback(table=table), protection)
    assert (result.candidate, result.failed) == expected


@pytest.mark.parametrize('changes', ({'valid': False}, {'position': 4}, {'taken': False},
    {'kind': 2}, {'kind': 3}))
def test_ineligible_or_correct_guidance_does_not_count_as_failure(changes):
    result = allocation(feedback(**changes), (3, 3))
    assert result.wrong_position is None and not result.failed


def test_miss_allocation_can_succeed_and_protected_longer_tables_can_block():
    assert allocation(feedback(hit=False), (0, 3)).candidate == 0
    assert allocation(feedback(hit=False), (3, 0)).candidate == 1
    assert allocation(feedback(hit=False), (3, 3)).failed


def test_earlier_wrong_branch_owns_allocation_not_later_high_provider():
    f = feedback()
    early = Source(True, 1, False, 0, 0, False, True)
    result = allocation(replace(f, sources=(f.sources[0], early)), (0, 0))
    assert (result.wrong_position, result.provider, result.candidate) == (1, None, 0)


def test_exact_threshold_counts_events_resets_at_maintenance_then_counts_new_failures():
    ledger = FailureLedger()
    failed = allocation(feedback(), (0, 0))
    success = allocation(feedback(table=0), (3, 0))
    for _ in range(127):
        ledger.apply(failed)
        ledger.apply(None)
        ledger.apply(success)
    assert (ledger.count, ledger.failures, ledger.ages, ledger.successes) == (127, 127, 0, 127)
    ledger.apply(failed)
    assert ledger.aging and ledger.count == 128
    ledger.apply(None)
    assert (ledger.count, ledger.failures, ledger.ages) == (0, 128, 1)
    ledger.apply(failed)
    assert (ledger.count, ledger.failures, ledger.ages) == (1, 129, 1)


@pytest.mark.parametrize('protection', ((0,), (0, 4), (-1, 0), (False, 0)))
def test_incomplete_or_nonsemantic_protection_is_rejected(protection):
    with pytest.raises(ValueError):
        allocation(feedback(), protection)


def test_complete_aging_is_not_reward_then_half_or_penalty_then_decrement():
    before = (tuple(index % 4 for index in range(512)), tuple(index % 4 for index in range(512)))
    after = aged(before)
    assert after[0][:4] == (0, 0, 1, 2) and after[1][:4] == (0, 0, 1, 1)
    assert len(after[0]) == len(after[1]) == 512
    with pytest.raises(ValueError):
        aged(((1,), (1,)))


class Program(PositiveProgram):
    """Synthetic actuals test checker plumbing; they earn no DUT coverage."""
    def make_checks(self, pc, tag_class):
        return EarlyAgingChecks(EarlyAgingCoverage(), pc)

    def quiet(self):
        idle = SourceProgram.quiet(self)
        if self.checks.confirm_age is not None:
            self.step(idle)
        return idle

    def step(self, event=None, *, mutate=None):
        event = self.event if event is None else event
        cycle = self.model.evaluate(event)
        self.tick += 2
        sources = self.model.sources
        observed = actual_live(sources, cycle.enabled[1])
        observed['fast'] = actual_fast(sources, cycle)
        learning = sources.short.learning
        decision = None if learning is None else allocation(learning.feedback, learning.useful)
        age = int(sources.short.low_tick == 128)
        observed['maintenance'] = dict(low=sources.short.low_tick, fire=int(learning is not None),
            need=0 if decision is None else int(decision.wrong_position is not None),
            mask=0 if decision is None else decision.mask,
            tables=tuple(dict(age=age, allocate=0, update=0) for _ in range(2)))
        if mutate is not None:
            mutate(observed)
        self.checks.candidates(dict(observed=dict(early_direction=observed)), event, cycle,
                               self.model, 'synthetic', None)
        self.checks.reached(self.tick)
        expected, actual = live_values(sources, cycle.enabled[1], observed)
        self.checks.check(expected, actual, 'synthetic complete live observation')
        expected, actual = fast_values(sources, cycle, observed['fast'])
        self.checks.check(expected, actual, 'synthetic complete owned guidance')
        for token, stage, repair in ((cycle.tokens[1], 2, cycle.middle_repair),
                                     (cycle.tokens[2], 3, cycle.final_repair)):
            if token is not None and repair:
                self.corrections.setdefault(token.sequence, []).append((self.tick, stage))
        self.model.advance(event)
        self.checks.checked(self.tick)
        return cycle

    def steer_live(self, source, goal):
        source = self.query(source)
        for _ in range(4):
            counter = main_counter(source.token)
            if counter == goal:
                return self.until(source, lambda token: main_counter(token) == goal
                    and steady_history(token, 2 if goal else FALLBACK))
            idle = self.quiet()
            taken = counter < goal
            request = self.feedback(source.token, 2, Kind.CONDITIONAL, taken)
            request = replace(request, branches=(replace(request.branches[0], mispredict=(counter >= 2) != taken),))
            self.step(replace(idle, feedback=request))
            accepted = self.tick
            self.quiet()
            self.checks.resolved(source, (accepted, request))
            source = self.query(source)
        raise AssertionError('normal direction endpoint did not become visible')

    def maintained(self):
        source = self.positive()
        self.checks.positive_consumer(source)
        self.checks.seed_history(self.checks.strong, False)
        source = self.until(source, lambda token: steady_history(token, 2)
            and (value := provider(self.model.sources, token)) is not None and value.counter >= 4)
        self.checks.seed_history(source, True)
        self.enable(False)
        for _ in range(8):
            source = self.query(source)
            if steady_history(source.token, FALLBACK):
                break
        else:
            raise AssertionError('fresh fallback history did not become available')
        self.enable(True)
        source = self.until(source, lambda token: AGE_RULES[0] in self.checks.reached_rules
            and main_counter(token) == 3 and steady_history(token, 2))
        for _ in range(44):
            source = self.steer_live(source, 3)
            if self.checks.ledger.ages:
                return source
            source = self.steer_live(source, 0)
        raise AssertionError('normal failure program did not reach maintenance')


def test_normal_autonomous_program_counts_128_real_failures_and_observes_parent_gap():
    program = Program()
    source = program.maintained()
    checks = program.checks
    assert checks.ledger.failures >= 128
    assert (checks.ledger.count, checks.ledger.ages) == (checks.ledger.failures - 128, 1)
    assert checks.confirm_age is None and checks.age_tick is not None
    assert all(rule in checks.reached_rules for rule in AGE_RULES[:6])
    assert checks.coverage.groups['checked'].coverage == 0
    _, _, positive = checks.history_seeds[True]
    source = program.until(source, lambda token:
        (value := provider(program.model.sources, token)) is not None and value.counter >= 4
        and (value.key, value.tag, value.position) == (positive.key, positive.tag, positive.position))
    checks.consumed(source, True)
    negative = program.steer(source, 0)
    program.enable(True)
    seed = checks.history_seeds[False][2]
    negative = program.until(negative, lambda token: steady_history(token, FALLBACK)
        and (value := provider(program.model.sources, token)) is not None
        and (value.key, value.tag, value.position) == (seed.key, seed.tag, seed.position)
        and value.counter < 4)
    checks.consumed(negative, False)
    checks.finish_aging(program.named)
    assert checks.closed and all(group.coverage == 100 for group in checks.coverage.groups.values())


@pytest.mark.parametrize('field', ('counter', 'fire', 'short-age', 'long-age'))
def test_bad_actual_maintenance_controls_latch_without_checked_credit(field):
    program = Program()
    def corrupt(actual):
        control = actual['maintenance']
        if field == 'counter':
            control['low'] += 1
        elif field == 'fire':
            control['fire'] ^= 1
        else:
            control['tables'][int(field == 'long-age')]['age'] ^= 1
    with pytest.raises(AssertionError) as first:
        program.step(mutate=corrupt)
    with pytest.raises(AssertionError) as repeated:
        program.checks.finish_aging()
    assert repeated.value is first.value and program.checks.coverage.groups['checked'].coverage == 0


def test_a_cancelled_next_guidance_cannot_be_resurrected_by_actual_valid():
    program = Program()
    program.checks.next_must_be_empty = 123  # Pure checker fixture, not a DUT state seed.
    with pytest.raises(AssertionError):
        program.step(replace(program.event, prediction_ready=False),
            mutate=lambda actual: actual['fast'].update(valid=1))
    assert program.checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('table,index', ((0, 0), (0, 511), (1, 0), (1, 511)))
def test_complete_poststate_check_does_not_hide_an_untouched_cell(table, index):
    program = Program()
    program.checks.confirm_age = (1, all_protection(program.model.sources.short.useful))
    def corrupt(actual):
        values = [list(row) for row in actual['useful']]
        values[table][index] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    with pytest.raises(AssertionError):
        program.step(mutate=corrupt)
    assert program.checks.coverage.groups['checked'].coverage == 0


def test_consumer_without_actual_maintenance_cannot_close_a_requirement():
    program = Program()
    with pytest.raises(AssertionError):
        program.checks.consumed(NS(prediction_tick=9999), True)
    assert program.checks.coverage.groups['checked'].coverage == 0


def test_event_ledger_does_not_import_a_cycle_model_or_signal_interface():
    import ast
    from pathlib import Path
    import suites.frontend.bpu.bpu.model.early_aging as module
    tree = ast.parse(Path(module.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert imports == ['dataclasses']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('distance', (0, 1, 10))
def test_fresh_recovery_owner_stays_inside_conservative_physical_history_window(distance):
    assert require_recovery_window(524, 524-distance, capacity=52, history_bits=31, shift=2) == distance*2


@pytest.mark.parametrize('source', (525, 513, 66))
def test_live_logical_metadata_does_not_authorize_overwritten_or_younger_recovery(source):
    with pytest.raises(ValueError, match='retained history window'):
        require_recovery_window(524, source, capacity=52, history_bits=31, shift=2)
