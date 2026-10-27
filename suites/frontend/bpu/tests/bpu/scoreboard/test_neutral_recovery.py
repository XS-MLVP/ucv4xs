"""Independent full-pipeline feasibility and adversarial actual comparisons."""
from dataclasses import replace
from pathlib import Path
import ast
import pytest
from bpuverify.bpu.checker.neutral_recovery import Checks
from bpuverify.bpu.coverage.neutral_recovery import Coverage
from bpuverify.bpu.model.neutral_recovery import PROFILES, STEPS, rules
from bpuverify.bpu.model.early_positive_protection import OLDER_PATHS
from bpuverify.bpu.model.early_opposition import provider
from tests.bpu.scoreboard.test_early_positive_protection import Program as SourceProgram


class Program(SourceProgram):
    def make_checks(self, pc, tag_class): return Checks(Coverage(), self.mode, pc)
    def seed(self):
        source = self.prepared_positive(); self.checks.arm_seed()
        source = self.base_bias(source, True); self.checks.seed_ready()
        return source
    def edge(self, source, name, *, taken, older=None, mutate=None):
        self.quiet(); self.checks.arm(name)
        source = self.original_taken(source, older=older, expect_taken=taken, mutate=mutate)
        assert name in self.checks.confirmed
        self.checks.owned_edge(name, source)
        return source
    def first_error(self):
        source = self.seed(); source = self.steer(source, 0)
        return self.edge(source, 'T-error-to-zero', taken=True, older=OLDER_PATHS[0])
    def complete(self):
        if self.mode == 'neutral-lower':
            source = self.first_error(); source = self.base_bias(source, False)
            source = self.edge(source, 'neutral-at-zero', taken=False, older=OLDER_PATHS[0])
            source = self.steer(source, 3)
            source = self.edge(source, 'first-NT-error', taken=False)
            source = self.edge(source, 'NT-error-restores-T', taken=False)
            source = self.base_bias(source, False); source = self.steer(source, 3)
            source = self.edge(source, 'contribution-restores-protection', taken=True)
        else:
            source = self.seed()
            for _ in range(3): source = self.original_taken(source)
            for name in ('approach-upper', 'reach-upper'):
                source = self.base_bias(source, False); source = self.steer(source, 3)
                source = self.edge(source, name, taken=True)
            source = self.base_bias(source, True)
            source = self.edge(source, 'neutral-at-upper', taken=True)
            source = self.steer(source, 0)
            source = self.edge(source, 'error-releases-upper', taken=True, older=OLDER_PATHS[1])
        source = self.steer(source, 3); source = self.original_taken(source)
        self.checks.fresh_consumer(source); self.quiet()
        return source


@pytest.mark.parametrize('profile', PROFILES)
async def test_full_independent_BPU_path_keeps_neutral_and_recovery_meanings_distinct(profile):
    program = Program(profile); source = program.complete(); checks = program.checks
    assert set(checks.owned) == {step.name for step in STEPS[profile]}
    assert len({row['owner'] for row in checks.owned.values()}) == len(STEPS[profile])
    assert checks.boundaries.groups['checked'].coverage == 0
    checks.finish_boundaries(program.named)
    assert checks.boundaries.closed and checks.boundaries.groups['checked'].coverage == pytest.approx(
        100*len(rules(profile))/sum(len(rules(p)) for p in PROFILES))
    neutral = checks.owned['neutral-at-zero' if profile == 'neutral-lower' else 'neutral-at-upper']['effect']
    assert neutral['kind'] == 'neutral' and neutral['before'] == neutral['after']
    if profile == 'neutral-lower': assert (neutral['counter_before'], neutral['counter_after']) == (3, 2)
    assert provider(program.model.sources, source.token).counter == STEPS[profile][-1].counter_after


@pytest.mark.parametrize('fault', ('target-protection', 'other-protection'))
async def test_a_neutral_hold_cannot_hide_direction_loss_or_state_pollution(fault):
    program = Program('neutral-lower'); source = program.first_error(); checks = program.checks
    source = program.base_bias(source, False); seen = []
    def corrupt(actual):
        if checks.pending is None or checks.pending[1].kind != 'neutral': return
        seen.append(program.tick)
        table, index = checks.identity.key if fault == 'target-protection' else (1, 511)
        values = [list(row) for row in actual['useful']]; values[table][index] ^= 1
        actual['useful'] = tuple(tuple(row) for row in values)
    with pytest.raises(AssertionError): program.edge(source, 'neutral-at-zero', taken=False, older=OLDER_PATHS[0], mutate=corrupt)
    assert len(seen) == 1
    assert checks.boundaries.groups['checked'].coverage == 0


async def test_fresh_public_counter_rejects_lost_neutral_direction_learning():
    program = Program('neutral-lower'); source = program.first_error(); checks = program.checks
    source = program.base_bias(source, False)
    source = program.edge(source, 'neutral-at-zero', taken=False, older=OLDER_PATHS[0])
    source = program.steer(source, 3); seen = []
    def corrupt(actual):
        for entry in actual['meta']['entries']:
            if entry['valid'] and entry['hit'] and entry['provider'] == 0 and entry['counter'] == 2:
                entry['counter'] = 3; seen.append(program.tick)
    step = program.step
    def damaged(event=None, **kwargs):
        kwargs['mutate'] = corrupt
        return step(event, **kwargs)
    program.step = damaged
    with pytest.raises(AssertionError): program.edge(source, 'first-NT-error', taken=False)
    assert len(seen) == 1 and checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('wrong-kind', 'stopped-direction', 'false-reward', 'wrong-owner'))
async def test_phase_association_requires_exact_semantics_and_bounded_original(fault):
    program = Program('neutral-lower'); source = program.first_error(); checks = program.checks
    source = program.base_bias(source, False)
    original = checks.boundary_for
    def damaged(event):
        if event.kind == 'neutral':
            changes = dict(kind='reward') if fault == 'wrong-kind' else dict(counter_after=event.counter_before) if fault == 'stopped-direction' else dict(after=1) if fault == 'false-reward' else dict(owner=event.owner+10000)
            event = replace(event, **changes)
        return original(event)
    checks.boundary_for = damaged
    with pytest.raises(AssertionError): program.edge(source, 'neutral-at-zero', taken=False, older=OLDER_PATHS[0])
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('missing', ('original-receipt', 'final-consumer', 'actual-confirmation', 'original-snapshot', 'edge-signature'))
async def test_incomplete_real_source_chain_never_gets_checked_credit(profile, missing):
    program = Program(profile); program.complete(); checks = program.checks
    name = STEPS[profile][-1].name
    if missing == 'original-receipt': checks.owned.pop(name)
    elif missing == 'final-consumer': checks.final = None
    elif missing == 'actual-confirmation': checks.pending = ('not-yet-compared',)
    elif missing == 'original-snapshot':
        seed = checks.original_seed; checks.original_seed = replace(seed, snapshot=replace(seed.snapshot, end_position=15))
    else:
        event, written, actual = checks.confirmed[name]
        checks.confirmed[name] = replace(event, kind='neutral'), written, actual
    with pytest.raises(AssertionError): checks.finish_boundaries(program.named)
    assert checks.boundaries.groups['checked'].coverage == 0


@pytest.mark.parametrize('profile', PROFILES)
async def test_unarmed_preparation_does_not_take_a_declared_edge(profile):
    program = Program(profile); program.seed(); checks = program.checks
    assert checks.boundary_for(None) is None and not checks.confirmed
    with pytest.raises(AssertionError): checks.arm(STEPS[profile][-1].name)


@pytest.mark.parametrize('profile,missing', [(profile, rule) for profile in PROFILES for rule in rules(profile)])
def test_atomic_checked_credit_requires_every_profile_obligation(profile, missing):
    wanted = rules(profile)
    coverage = Coverage()
    for rule in wanted:
        if rule != missing:
            coverage.record(profile, 'reached', rule, 100); coverage.record(profile, 'checked', rule, 200)
    with pytest.raises(AssertionError): coverage.finish(profile)
    assert coverage.groups['checked'].coverage == 0


def test_semantic_case_hides_native_timing_and_io():
    for name in ('tests/bpu/testcase/test_neutral_recovery.py', 'bpuverify/bpu/case/neutral_recovery.py'):
        tree = ast.parse(Path(name).read_text())
        forbidden = {'ClockCycles', 'RisingEdge', 'FallingEdge', 'get_', 'set_', 'gather', 'create_task'}
        assert not {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & forbidden
