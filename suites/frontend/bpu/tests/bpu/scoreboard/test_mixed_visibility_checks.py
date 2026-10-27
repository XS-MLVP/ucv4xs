"""Synthetic adversarial observations must fail; they never count as DUT events."""
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.model.tage.mixed_visibility import PROGRAMS, PRELUDE_PLAN
from tests.bpu.scoreboard.mixed_visibility_fixtures import (
    armed, held, prepared, mixed, relearned, released, completed, packet)
from tests.bpu.scoreboard.test_partial_reuse import transfer


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_all_partial_and_final_services_and_twelve_consumers_required_before_checked(program):
    checks, _, retired = completed(program)
    assert tuple(map(len, checks.written.values())) == tuple(1 + len(p) for p in program.final_plan)
    assert len(checks.consumers) == 12 and not retired
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    assert len(retired) == len(set(retired))
    with pytest.raises(AssertionError, match='single-use'):
        checks.finish()


@pytest.mark.parametrize('program_index,fault', (
    (0, 'wrong-owner'), (0, 'pending-peer-lost'), (1, 'missing-proposal'),
    (2, 'saturated-write-not-suppressed'), (3, 'stale-new-source'), (3, 'wrong-tag'), (0, 'reread')))
def test_new_actual_proposals_keep_old_or_mixed_source_qualification_and_all_pending_neighbors(program_index, fault):
    checks, _, _ = relearned(PROGRAMS[program_index])
    checks.offered = checks.offered[:3]
    row = packet(checks, index=3, plan=checks.program.pending_before(0))
    active = next(p for p in row['state']['incoming'] if p['valid'])
    if fault == 'wrong-owner': row['owner_hits'][0].update(owner0=(1, 0, 0), owner1=0)
    elif fault == 'pending-peer-lost': row['state']['dirty'] = ((0, 0, 0, 0),) * 2
    elif fault == 'missing-proposal': active['valid'] = 0
    elif fault == 'saturated-write-not-suppressed': row['state']['incoming'][1].update(valid=1, bits=checks.payload(('target-a', 0)))
    elif fault == 'stale-new-source': active['bits']['counter'] = 1
    elif fault == 'wrong-tag': active['bits']['tag'] ^= 1
    else: row['state']['reads'][1]['valid'] = 1
    before = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=40308), row)
    # No proposal is a missing observation, not a silently accepted correct beat.
    if fault == 'missing-proposal':
        checks.refill_qualified = False
        with pytest.raises(AssertionError): checks.pending()
    else:
        with pytest.raises(AssertionError) as first: checks.raise_failure()
        with pytest.raises(AssertionError) as second: checks.finish()
        assert first.value is second.value
    assert checks.pipeline.model.sources.tage.state() == before
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program_index,fault', ((0, 'paired-by-ordinal'), (1, 'extra-owner0'),
    (2, 'suppressed-target-a'), (3, 'stale-neighbor-b'), (0, 'wrong-tag'), (2, 'before-release')))
def test_wrong_or_extra_sdk_results_cannot_be_hidden_by_unequal_owner_counts(program_index, fault):
    checks, _, _ = released(PROGRAMS[program_index])
    owner, tick = 0, 40510
    value = deepcopy(checks.expected_plan[owner][0])
    if fault == 'paired-by-ordinal': value = deepcopy(checks.expected_plan[1][0])
    elif fault == 'extra-owner0':
        checks.write_accepted(0, transfer(tick, value)); tick += 2
    elif fault == 'suppressed-target-a': owner, value = 1, checks.payload(('target-a', 0))
    elif fault == 'stale-neighbor-b': owner, value = 1, checks.payload(('neighbor-b', 6))
    elif fault == 'wrong-tag': value['tag'] ^= 1
    else: tick = checks.release_tick
    with pytest.raises(AssertionError):
        checks.write_accepted(owner, transfer(tick, value))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', (('initial', 'original'), ('initial', 'neighbor'), ('mixed', 'original'),
    ('mixed', 'neighbor'), ('blocked', 'displaced'), ('serviced', 'original')))
def test_each_real_visibility_boundary_has_required_consumers(phase, name):
    checks, _, _ = completed(PROGRAMS[0])
    del checks.consumers[phase, name]
    with pytest.raises(AssertionError, match='twelve'):
        checks.finish()


def test_original_metadata_is_not_rebased_when_mixed_learning_is_armed():
    checks, _, _ = mixed(PROGRAMS[1])
    checks.saved['old-target'].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError, match='saved input'):
        checks.arm_mixed()
    assert checks.coverage.groups['checked'].coverage == 0


def test_service_preparation_does_not_replace_actual_acceptance_or_allow_a_full_drain():
    checks, _, _ = held(PROGRAMS[0])
    checks.pipeline.last_tick = 40090
    checks.begin_partial(Future(), Future()); prepared(checks)
    with pytest.raises(AssertionError, match='only one'):
        checks.partial_complete(NS(tick=40100))
    checks, _, _ = mixed(PROGRAMS[0])
    with pytest.raises(AssertionError, match='declared released'):
        checks.write_accepted(0, transfer(40104, checks.payload(('target-b', 6))))


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_missing_last_service_and_changed_snapshot_cannot_get_checked(program):
    checks, _, _ = completed(program)
    checks.requests[0].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError, match='immutable'):
        checks.finish()
    checks, _, _ = released(program)
    for owner, versions in enumerate(checks.expected_plan):
        for index, payload in enumerate(versions[:-1]):
            checks.write_accepted(owner, transfer(40510 + 2 * index, payload))
    with pytest.raises(AssertionError, match='all declared'):
        checks.services_complete()


def test_unreviewed_program_cannot_add_physical_labels_to_coverage_or_checks():
    from bpuverify.bpu.coverage.mixed_visibility import MixedVisibilityCoverage
    from bpuverify.bpu.checker.mixed_visibility import MixedVisibilityChecks
    foreign = replace(PROGRAMS[0], name='physical-rank-2')
    with pytest.raises(ValueError, match='unknown'): MixedVisibilityCoverage(foreign)
    with pytest.raises(ValueError, match='unknown'): MixedVisibilityChecks(None, None, foreign)
