"""Targeted synthetic faults, separate from four actual DUT program results."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from suites.frontend.bpu.bpu.model.tage.partial_residency import PROGRAMS
from tests.bpu.scoreboard.partial_residency_fixtures import armed, held, drain, packet, completed


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_checked_requires_every_actual_phase_and_all_complete_source_snapshots(program):
    checks, _, retired = completed(program)
    assert checks.coverage.groups['checked'].coverage == 0 and not retired
    checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    assert len(retired) == len(program.source_names)
    with pytest.raises(AssertionError):
        checks.finish()


@pytest.mark.parametrize('program_index,fault', (
    (0, 'wrong-valid-port'), (1, 'victim-counter'), (2, 'wrong-tag'), (3, 'wrong-row'),
    (0, 'old-requested-owner'), (1, 'spurious-hit'), (2, 'victim-not-pending'), (3, 'missing-input'),
))
def test_bad_actual_proposal_or_identity_precondition_latches_first_error_without_model_repair(program_index, fault):
    checks, _, _ = armed(PROGRAMS[program_index])
    checks.begin_stage(0)
    checks.begin_read_window()
    checks.capture_state(NS(tick=40000), packet(checks, training=True))
    if fault != 'missing-input' and len(checks.stage.sources) > 1:
        checks.capture_state(NS(tick=40002), packet(checks, training=True))
    index = 1 if fault == 'victim-not-pending' else 0
    if index:
        checks.capture_state(NS(tick=40008), packet(checks, index=0))
    row = packet(checks, index=index)
    active = next(p for p in row['state']['incoming'] if p['valid'])
    if fault == 'wrong-valid-port':
        row['state']['incoming'] = tuple(reversed(row['state']['incoming']))
    elif fault == 'victim-counter': active['bits']['counter'] = 1
    elif fault == 'wrong-tag': active['bits']['tag'] ^= 1
    elif fault == 'wrong-row': active['bits']['row'] ^= 1
    elif fault == 'old-requested-owner': row['owner_hits'][0].update(owner0=(1, 0, 0), owner1=0)
    elif fault == 'spurious-hit': row['owner_hits'][1]['owner1'] = 1
    elif fault == 'victim-not-pending': row['state']['dirty'] = ((0, 0, 0, 0),) * 2
    else: checks.input_ticks.clear()
    before = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=40010), row)
    with pytest.raises(AssertionError) as first:
        checks.raise_failure()
    with pytest.raises(AssertionError) as second:
        checks.finish()
    assert first.value is second.value
    if fault == 'victim-not-pending':
        assert 'prestate' in str(first.value)
    assert checks.pipeline.model.sources.tage.state() == before
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program_index,fault', (
    (0, 'wrong-owner'), (1, 'victim-counter'), (2, 'victim-tag'),
    (3, 'before-release'), (2, 'duplicate'),
))
def test_bad_sdk_service_cannot_replace_latest_complete_identity(program_index, fault):
    checks, reference, _ = armed(PROGRAMS[program_index])
    held(checks, reference)
    from tests.bpu.scoreboard.partial_residency_fixtures import consumers
    consumers(checks, reference, 'blocked')
    checks.pipeline.last_tick = 40150
    checks.release()
    owner = next(o for o, p in enumerate(checks.expected_plan) if p)
    value = deepcopy(checks.expected_plan[owner][0])
    tick = 40160
    if fault == 'wrong-owner': owner = 1 - owner
    elif fault == 'victim-counter': value['counter'] = 1
    elif fault == 'victim-tag': value['tag'] = checks.identities['a']['tag']
    elif fault == 'before-release': tick = 40150
    else: checks.write_accepted(owner, NS(accepted_tick=tick, value=deepcopy(value)))
    with pytest.raises(AssertionError):
        checks.write_accepted(owner, NS(accepted_tick=tick, value=value))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
@pytest.mark.parametrize('phase,name', (('blocked', 'original'), ('blocked', 'displaced'),
                                      ('serviced', 'original'), ('serviced', 'displaced')))
def test_missing_any_required_consumer_prevents_all_checked_credit(program, phase, name):
    checks, _, _ = completed(program)
    del checks.records[-1]['consumers'][phase, name]
    with pytest.raises(AssertionError):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_changed_original_metadata_is_never_rebased_to_a_current_identity(program):
    checks, _, _ = completed(program)
    next(iter(checks.saved.values())).meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError):
        checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_missing_acceptances_and_repeated_pending_or_service_completion_are_rejected():
    checks, reference, _ = armed(PROGRAMS[1])
    held(checks, reference)
    checks.accepted.clear()
    checks.pending_ready = False
    with pytest.raises(AssertionError, match='acceptances'):
        checks.pending()
    checks, reference, _ = armed(PROGRAMS[1])
    held(checks, reference)
    with pytest.raises(AssertionError, match='single-use'):
        checks.pending()
    checks, reference, _ = armed(PROGRAMS[1])
    held(checks, reference)
    drain(checks, reference)
    with pytest.raises(AssertionError, match='once'):
        checks.services_complete()


@pytest.mark.parametrize('kind', ('coverage', 'checker'))
def test_unregistered_semantic_program_cannot_expand_coverage_or_change_expectations(kind):
    from suites.frontend.bpu.bpu.coverage.partial_residency import PartialResidencyCoverage
    from suites.frontend.bpu.bpu.checker.partial_residency import PartialResidencyChecks
    foreign = replace(PROGRAMS[0], name='unreviewed-variant')
    with pytest.raises(ValueError, match='unknown'):
        if kind == 'coverage':
            PartialResidencyCoverage(foreign)
        else:
            PartialResidencyChecks(None, None, foreign)
