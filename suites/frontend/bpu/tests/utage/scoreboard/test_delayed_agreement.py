"""Nonzero agreement qualification and direction learning are separate duties."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import pytest
from bpuverify.utage.model.delayed_agreement import PROGRAMS, Program, RULES
from bpuverify.utage.coverage.delayed_agreement import Coverage
from tests.utage.scoreboard.test_delayed_protection import exercise


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
def test_original_agreement_holds_one_and_does_not_cancel_direction_or_subsequent_learning(p):
    checks, monitor, _ = exercise(p); checks.finish(monitor)
    assert checks.closed and checks.compared == len(checks.feedback.consumed) == 12
    assert len(checks.origins) == 12 and len(checks.late) == 8 and len(checks.consumers) == 14
    assert len(checks.originals) == 24
    for owner in (0, 1):
        agreement = p.step('late-agreement', owner)
        assert agreement.before.taken == agreement.base == agreement.actual != agreement.current.taken
        assert agreement.current.useful == agreement.after.useful == 1
        assert agreement.current.counter != agreement.after.counter
        assert monitor.records[agreement.ordinal]['changes'] == ()
        assert monitor.records[agreement.ordinal]['versions']['0']['new_cell'] == agreement.counter_cell
        assert checks.late['late-agreement', owner]['actual_effect_tick'] is not None
        assert p.step('late-restore', owner).after.useful == 2
        assert p.step('late-wrong', owner).after.useful == 1


@pytest.mark.parametrize('phase', ('late-agreement', 'late-restore'))
@pytest.mark.parametrize('owner', (0, 1))
@pytest.mark.parametrize('fault', ('zero-protection', 'original-counter', 'wrong-identity', 'current-prediction', 'wrong-source-age', 'uncompared-owner'))
def test_source_and_current_nonzero_prestate_cannot_be_substituted(phase, owner, fault):
    checks, _, args = exercise(PROGRAMS[0], stop=(phase, owner))
    step, cell, latest, tick, protection = args
    if fault == 'zero-protection':
        protection = list(protection); protection[step.indices[0]] = 0
    elif fault == 'original-counter': cell['counter'] = step.before.counter
    elif fault == 'wrong-identity': cell['tag'] ^= 1
    elif fault == 'current-prediction':
        origin = checks.origins[phase, owner]
        origin['source'] = replace(origin['source'], taken=step.current.taken)
    elif fault == 'wrong-source-age': checks.origins[phase, owner]['completed'] = 0 if phase == 'late-agreement' else tick-1
    else: checks.compared = 0
    with pytest.raises(AssertionError): checks.before_late(step, cell, latest, tick, tuple(protection))


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('fault', ('false-penalty', 'false-reward', 'direction-not-learned', 'old-counter-rebase', 'missing-write', 'later-restoration-lost'))
def test_unchanged_protection_is_not_sufficient_without_qualified_direction_learning(p, fault):
    checks, monitor, _ = exercise(p)
    step = p.step('late-agreement', 0); row = monitor.records[step.ordinal]
    if fault == 'false-penalty': row['changes'] = ((step.indices[0], 1, 0),)
    elif fault == 'false-reward': row['changes'] = ((step.indices[0], 1, 2),)
    elif fault == 'direction-not-learned': row['versions']['0']['new_cell']['counter'] = step.current.counter
    elif fault == 'old-counter-rebase': row['versions']['0']['new_cell']['counter'] = step.before.counter-1
    elif fault == 'missing-write': row['versions'].pop('0')
    else:
        restore = p.step('late-restore', 0)
        monitor.records[restore.ordinal]['changes'] = ()
    checks.compared = 0
    with pytest.raises(AssertionError) as error: checks.prefix(monitor, 12)
    assert error.value.context.request['point']


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('missing', ('agreement-source', 'agreement-effect', 'agreement-consumer', 'restoration-source', 'long-consumer', 'original-base', 'actual-cadence'))
def test_every_source_preservation_and_consumer_remains_mandatory(p, missing):
    checks, monitor, _ = exercise(p)
    if missing == 'agreement-source': checks.origins.pop(('late-agreement', 1))
    elif missing == 'agreement-effect': checks.late['late-agreement', 1]['actual_effect_tick'] = None
    elif missing == 'agreement-consumer': checks.consumers.pop(('late-agreement', 1))
    elif missing == 'restoration-source': checks.origins.pop(('late-restore', 0))
    elif missing == 'long-consumer': checks.consumers.pop(('final-long', 1))
    elif missing == 'original-base':
        source = checks.origins['late-agreement', 0]['source']
        source.meta['abtbResult'][0]['baseTaken'] ^= 1
    else: checks.cadences.pop()
    with pytest.raises(AssertionError): checks.finish(monitor)


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('missing', RULES)
def test_checked_credit_waits_for_the_full_nonzero_agreement_cohort(p, missing):
    coverage = Coverage(p)
    for rule in RULES:
        if rule != missing: coverage.reach(rule)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
def test_complete_cohort_has_only_its_own_semantic_bins(p):
    coverage = Coverage(p)
    for rule in RULES: coverage.reach(rule)
    coverage.finish(); assert coverage.groups['checked'].coverage == 25
    with pytest.raises(AssertionError): coverage.finish()
    with pytest.raises((AttributeError, TypeError)): p.initial_roles = ('flip',)


def test_case_hides_timing_and_program_is_not_a_storage_coordinate():
    with pytest.raises(ValueError): Program('bank0', 'interleaved')
    with pytest.raises(ValueError): Program('serial', 'index128')
    for name in ('tests/utage/testcase/test_delayed_agreement.py', 'bpuverify/utage/case/delayed_agreement.py'):
        text = Path(name).read_text()
        assert not any(s in text for s in ('asyncio', 'ClockCycles', 'FallingEdge', 'RisingEdge', 'get_', 'set_'))
    tree = ast.parse(Path('bpuverify/utage/model/delayed_agreement.py').read_text())
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))
