"""Logical histories, owned windows and explicit recovery-view distinctions."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from bpuverify.bpu.model.common_history import Value
from bpuverify.bpu.model.common_query import CommonQueryReference
from bpuverify.bpu.model.pipeline import Events, PipelineReference, Redirect
from bpuverify.bpu.model.selection import Branch, Choice, Kind

PC = 0x40000800


class LoopSources:
    """Unit-test instruction semantics, not DUT observations or learned state."""
    def reset(self):
        pass

    def capture(self, pc, checkpoint):
        return SimpleNamespace(values=lambda: {'0.valid': 1, '0.position': 1, '0.kind': Kind.CONDITIONAL})

    def choose(self, token, stage, enabled):
        return Choice(Branch(1, token.pc, Kind.CONDITIONAL), 0, 'main')

    def advance(self, events, cycle, issued):
        pass

    def validate(self, events, cycle):
        pass


class Harness:
    def __init__(self):
        self.pipeline = PipelineReference(LoopSources())
        self.query = CommonQueryReference()
        self.events = Events(PC, initialization_complete=True)
        self.last = None

    def step(self, *, ready=True, recovery=None):
        events = replace(self.events, prediction_ready=ready)
        if recovery is not None:
            source, correction = recovery
            events = replace(events, redirect=Redirect(source.owner,
                (source.pc // 16) * 16 + correction.position, correction.target, correction.taken))
        cycle = self.pipeline.evaluate(events)
        step = self.query.preview(cycle, recovery=recovery)
        self.pipeline.advance(events)
        issued = self.pipeline.stages[0] if cycle.fires[0] else None
        self.query.apply(step, issued=issued)
        self.last = step
        return step, issued

    def learned_loop(self):
        for _ in range(24):
            self.step()
        assert self.query.value == Value(True, 65535, 255)
        token = next(reversed(self.pipeline.published.values()))
        source = self.query.snapshot(token)
        assert source.published and source.metadata == Value(True, 65535, 255)
        return token, source


def test_every_query_reads_its_own_completed_window_not_the_latest_cursor():
    h = Harness()
    views = []
    for _ in range(20):
        step, issued = h.step()
        if issued is not None:
            source = h.query.snapshot(issued)
            assert source.read == step.lookup
            views.append(source.read)
    assert views[:3] == [Value(), Value(), Value()]
    assert Value(True, 1, 1) in views and Value(True, 65535, 255) in views
    assert h.query.iterations.cursor > 0


@pytest.mark.parametrize('pause', (1, 3, 8))
def test_pausing_the_youngest_query_holds_its_original_while_older_work_completes(pause):
    h = Harness()
    h.learned_loop()
    token = h.pipeline.stages[0]
    original = h.query.snapshot(token)
    for _ in range(pause):
        step, issued = h.step(ready=False)
        assert issued is None and not step.iteration.issue
    assert h.pipeline.stages[0] is token
    assert h.query.snapshot(token) == original
    assert h.last.reason == ('no-query' if pause > 1 else h.last.reason)


@pytest.mark.parametrize('taken', (False, True))
def test_backend_placeholder_and_recomputed_prefix_do_not_rebind_the_original_read(taken):
    h = Harness()
    _, original = h.learned_loop()
    correction = Branch(1, PC + 0x100, Kind.CONDITIONAL, taken)
    first, token = h.step(recovery=(original, correction))
    assert first.reason == 'backend-placeholder' and first.lookup == Value(False, 65535, 255)
    raw = h.query.snapshot(token)
    assert raw.read == Value(False, 65535, 255)
    second, _ = h.step()
    expected = Value(False, 65535 if taken else 65534, 254)
    assert second.reason == 'backend-prefix' and second.lookup == expected
    for _ in range(3):
        h.step()
    published = h.query.snapshot(token)
    assert published.published and published.metadata == expected
    assert published.read == raw.read
    before = h.query.sc_history(token)
    after = h.query.sc_history(token, feedback=True)
    assert (before.global_history, before.backward) == (65535, 255)
    assert (after.global_history, after.backward) == (expected.ghr, expected.bw)
    assert before.loop == after.loop == 0


def test_published_original_is_unchanged_by_younger_loop_saturation_and_recovery():
    h = Harness()
    token, original = h.learned_loop()
    count = original.loop
    for _ in range(260):
        h.step()
    assert h.query.iterations.cursor == 255 and count < 255
    assert h.query.snapshot(token) is original
    step, issued = h.step(recovery=(original, Branch(1, PC, Kind.CONDITIONAL)))
    assert step.iteration.after == count + 1
    assert h.query.snapshot(issued).loop == count + 1
    assert h.query.snapshot(token) is original


@pytest.mark.parametrize('fault', ('equal-owner', 'other-PC', 'other-sequence', 'reset', 'retired'))
def test_a_matching_pc_or_equal_history_encoding_does_not_grant_query_ownership(fault):
    h = Harness()
    token, _ = h.learned_loop()
    bad = token
    if fault == 'equal-owner':
        bad = replace(token, history=replace(token.history))
    elif fault == 'other-PC':
        bad = replace(token, pc=token.pc + 1)
    elif fault == 'other-sequence':
        bad = replace(token, sequence=token.sequence + 1)
    elif fault == 'reset':
        h.query.reset()
    else:
        h.query.retire(token)
    with pytest.raises(ValueError, match='absent|another original'):
        h.query.snapshot(bad)


def test_unpublished_query_cannot_supply_backend_or_feedback_history():
    h = Harness()
    h.step()
    _, token = h.step()
    source = h.query.snapshot(token)
    assert not source.published
    with pytest.raises(ValueError, match='published original'):
        h.query.sc_history(token, feedback=True)
    cycle = h.pipeline.evaluate(h.events)
    with pytest.raises(ValueError, match='published original'):
        h.query.preview(cycle, recovery=(source, Branch(1, PC, Kind.CONDITIONAL)))


@pytest.mark.parametrize('fault', ('copied', 'replayed', 'foreign', 'stale'))
def test_query_boundary_plan_is_owned_and_single_use(fault):
    h = Harness()
    h.learned_loop()
    step, _ = h.step()
    if fault == 'copied':
        step = replace(step)
    elif fault == 'foreign':
        other = Harness()
        step = other.query.preview(other.pipeline.evaluate(other.events))
    elif fault == 'stale':
        h.query.reset()
    before = h.query.state()
    with pytest.raises(ValueError, match='stale|copied|foreign|consumed'):
        h.query.apply(step)
    assert h.query.state() == before


def test_pending_backend_recovery_keeps_its_source_until_recomputed():
    h = Harness()
    token, source = h.learned_loop()
    h.step(recovery=(source, Branch(1, PC, Kind.CONDITIONAL)))
    with pytest.raises(ValueError, match='pending recovery'):
        h.query.retire(token)
    h.step()
    h.query.retire(token)
    with pytest.raises(ValueError, match='absent'):
        h.query.snapshot(token)


from bpuverify.bpu.model.common_query import PROFILES, RULES
from bpuverify.bpu.coverage.common_query import CommonQueryCoverage, OBLIGATIONS


@pytest.mark.parametrize('profile,missing', tuple((profile, rule) for profile in PROFILES for rule in RULES[profile]))
def test_omitting_any_actual_history_obligation_cannot_award_checked_credit(profile, missing):
    coverage = CommonQueryCoverage(profile)
    for rule in RULES[profile]:
        if rule != missing:
            coverage.record(rule, 10)
    with pytest.raises(AssertionError, match='every actual query'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0
    assert not coverage.closed


@pytest.mark.parametrize('profile', PROFILES)
def test_closed_query_program_records_only_its_semantic_obligations(profile):
    coverage = CommonQueryCoverage(profile)
    assert len(OBLIGATIONS) == 46
    for number, rule in enumerate(RULES[profile]):
        coverage.record(rule, number)
    coverage.finish()
    report = coverage.groups['checked'].report()['points'][0]['counts']
    assert {name for name, count in report.items() if count} == {profile + '.' + rule for rule in RULES[profile]}
    with pytest.raises(AssertionError, match='every actual query'):
        coverage.finish()
