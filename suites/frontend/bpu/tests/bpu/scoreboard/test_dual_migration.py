"""Independent event programs and wrong synthetic observations; no DUT credit."""
from suites.frontend.bpu.models.configuration import TAGE_ALLOCATION_WAIT
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from toffee import Scoreboard
from suites.frontend.bpu.bpu.checker.dual_migration import DualMigrationChecks
from suites.frontend.bpu.bpu.coverage.dual_migration import DualMigrationCoverage, RULES
from suites.frontend.bpu.bpu.model.tage.dual_migration import PC, PATHS, OUTCOMES, preparation, counters_after
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC, STREAM_POSITION, learning_inflight
from suites.frontend.bpu.bpu.model.pipeline import Outcome, Resolution, Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from tests.bpu.scoreboard.test_direction_sources import prepared, quiet, revisit
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def source(model, token, tick):
    return NS(token=token, prediction_tick=tick, meta_tick=tick + 4,
              meta=NS(resolve=dict(sequence=token.sequence, fields=deepcopy(model.sources.defined_metadata(token)))))


def fixture(*, initial_pc=None, checks_type=DualMigrationChecks, coverage_type=DualMigrationCoverage):
    if initial_pc is None:
        model, event, anchor = prepared()
    else:
        from tests.bpu.scoreboard.test_semantic_pipeline import boot
        from tests.bpu.scoreboard.test_direction_sources import ENABLED
        from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources
        model, event = boot(DirectionSources(), pc=initial_pc)
        event = replace(event, enabled=ENABLED)
        for _ in range(8):
            cycle = model.advance(event)
            if cycle.metadata is not None and cycle.metadata.lookup is not None:
                anchor = cycle.metadata
                break
        else: raise AssertionError('independent initial source absent')
    retired = []
    pipeline = NS(model=model, board=Scoreboard('dual-migration-contract'), raise_failure=lambda: None,
        source_token=lambda s: s.token, retire_source=retired.append, last_tick=40000,
        last_resolution_controls=(40002, event.enabled))
    checks = checks_type(pipeline, coverage_type())
    stream_pc=getattr(checks,'stream_pc',STREAM_PC)
    if getattr(checks,'prepare_read_stream',True):
        loop = revisit(model, event, anchor, stream_pc)
        feedback = Resolution(loop.history, stream_pc,
            (Outcome(STREAM_POSITION, stream_pc, Kind.DIRECT, True, mispredict=True),), origin=loop)
        model.advance(replace(quiet(model, event), feedback=feedback)); quiet(model, event)
    for index, step in enumerate(checks.intents):
        idle = quiet(model, event)
        if event.enabled[3] != step.enabled:
            event = replace(event, enabled=tuple(step.enabled if i == 3 else x for i, x in enumerate(event.enabled)))
            for _ in range(3): model.advance(replace(idle, enabled=event.enabled))
        before_role=getattr(checks,'before_capture_roles',{}).get(step.name)
        if before_role is not None:
            checks.retain_prepared(before_role,source(model,via(model,event,anchor,PATHS[step.context]),1000*index+40))
        before = source(model, via(model, event, anchor, PATHS[step.context]), 1000 * index + 100)
        checks.preparing_input(before, step)
        request = resolution(before.token, step.outcomes)
        idle = quiet(model, event)
        if step.allocation is not None:
            feedback = model.sources.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                if model.sources.tage.allocation_at_next_accept(feedback) == step.allocation: break
                model.advance(idle)
            else: raise AssertionError(('semantic allocation opportunity absent', step))
        model.advance(replace(idle, feedback=request))
        after = source(model, via(model, event, anchor, PATHS[step.context]), 1000 * index + 200)
        checks.prepared(after, step, (1000 * index + 120, request))
        role=getattr(checks,'capture_roles',{}).get(step.name)
        if role is not None:
            checks.retain_prepared(role,after)
            count=getattr(checks,'prepared_source_count',lambda _:1)(role)
            for extra in range(count-1):
                checks.retain_prepared(role,source(model,via(model,event,anchor,PATHS[step.context]),
                                                  1000*index+220+extra*20))
        if step.save:
            checks.retain_old(after)
            for extra in range(checks.source_count - 1):
                checks.retain_old(source(model, via(model, event, anchor, PATHS['original']), 1000 * index + 220 + extra * 20))
    current_tick=max(30000,1000*len(checks.intents)+100)
    current = {n: source(model, via(model, event, anchor, p), current_tick + i * 20) for i, (n, p) in enumerate(PATHS.items())}
    checks.arm(current)
    return checks, (model, event, anchor), retired


def monitored_row(checks, *, dirty=0, proposals=False, training=False):
    return dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        prediction=dict(valid=1, ready=1, pc=STREAM_PC), training=dict(valid=int(training), ready=1),
        incoming=tuple(dict(valid=int(proposals), bits=deepcopy(p)) for p in checks.proposal),
        dirty=((dirty, 0, 0, 0),) * 2,
        writes=tuple(dict(valid=1, ready=0, bits=deepcopy(p)) for p in checks.pending_payload))


def held_fixture():
    checks, (model, event, anchor), retired = fixture()
    idle = quiet(model, event)
    model.advance(replace(idle, redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    for old in checks.sources[:2]: model.advance(replace(event, feedback=resolution(old.token, OUTCOMES)))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage): break
    else: raise AssertionError('both owned learnings did not mature')
    checks.begin_read_window()
    for tick in (40000, 40002): checks.capture_state(NS(tick=tick), monitored_row(checks, training=True))
    for index in range(2):
        checks.capture_state(NS(tick=40008 + 2 * index), monitored_row(checks, proposals=True, dirty=index))
    events = tuple((40000 + i * 2, resolution(s.token, OUTCOMES)) for i, s in enumerate(checks.sources[:2]))
    checks.pipeline.last_resolution_controls = 40002, event.enabled
    checks.accepted_burst(events); checks.pending()
    return checks, (model, event, anchor), retired


def old_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(PATHS.items()):
        mid = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, mid.history, PC, path + 4)
        checks.consume('blocked', name, source(model, token, 40100 + 20 * i))


def service_fixture():
    checks, program, retired = held_fixture(); old_consumers(checks, program)
    model, event, anchor = program
    checks.pipeline.last_tick = 40150; checks.release()
    for way, payload in enumerate(checks.pending_payload):
        checks.write_accepted(way, NS(accepted_tick=40160, value=deepcopy(payload)))
    quiet(model, event)
    for i, (name, path) in enumerate(PATHS.items()):
        checks.consume('serviced', name, source(model, via(model, event, anchor, path), 40200 + i * 20))
    return checks, program, retired


def completed_fixture():
    checks, (model, event, anchor), retired = service_fixture(); checks.begin_clean()
    row = monitored_row(checks, training=True); row['reads'][0]['valid'] = 0
    for p in row['writes']: p.update(valid=0, ready=1)
    checks.capture_state(NS(tick=40300), row)
    row['training']['valid'] = 0
    for p in row['incoming']: p['valid'] = 1
    checks.capture_state(NS(tick=40308), row)
    request = resolution(checks.sources[2].token, OUTCOMES)
    model.advance(replace(quiet(model, event), feedback=request)); quiet(model, event)
    checks.accepted_clean((40300, request))
    for way, payload in enumerate(checks.clean_payload):
        checks.write_accepted(way, NS(accepted_tick=40310, value=deepcopy(payload)))
    for i, (name, path) in enumerate(PATHS.items()):
        checks.consume('clean', name, source(model, via(model, event, anchor, path), 40400 + i * 20))
    return checks, retired


def test_normal_preparation_exchanges_both_logical_owners_without_seeding_model_state():
    checks, _, _ = fixture()
    assert len(checks.prepared_labels) == 24 and len(checks.sources) == 3
    assert checks.profile(checks.sources[0]) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0)))
    assert checks.profile(checks.before['original']) == ((0, 1), ((7, 1, 1, 0), (7, 0, 4, 0)))
    assert len({id(s.token.history) for s in checks.sources}) == 3
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('initial_pc', (PC, PC + 0x40))
def test_original_history_geometry_is_derived_not_a_fixed_row_from_a_different_boot(initial_pc):
    checks, _, _ = fixture(initial_pc=initial_pc)
    read = checks.read(checks.sources[0])
    assert {p['row'] for p in checks.proposal} == {read.rows[3]}
    assert checks.read(checks.before['displaced']).rows[3] == read.rows[3]
    assert checks.profile(checks.before['original']) == ((0, 1), ((7, 1, 1, 0), (7, 0, 4, 0)))


@pytest.mark.parametrize('count,expected', ((0, (1, 4)), (1, (0, 5)), (2, (0, 6)), (3, (0, 7))))
def test_three_distinct_old_sources_update_current_counters_not_repeated_old_snapshot(count, expected):
    assert counters_after(count) == expected


def test_blocked_then_clean_versions_only_close_after_all_four_actual_services_and_six_consumers():
    checks, retired = completed_fixture()
    assert checks.coverage.groups['checked'].coverage == 0 and not retired
    checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values()) and len(retired) == 11


@pytest.mark.parametrize('fault', ('missing-prepare', 'missing-old', 'current-owner', 'current-counter', 'displaced-hit'))
def test_arming_does_not_accept_an_incomplete_or_unmigrated_profile(fault):
    checks, _, _ = fixture()
    if fault == 'missing-prepare': checks.prepared_labels.pop()
    elif fault == 'missing-old': checks.sources.pop()
    else:
        actual = checks.profile
        def corrupt(s):
            if s is checks.before['original']:
                if fault == 'current-owner': return (0, 1), ((7, 0, 1, 0), (7, 1, 4, 0))
                if fault == 'current-counter': return (0, 1), ((7, 1, 2, 0), (7, 0, 5, 0))
            if fault == 'displaced-hit' and s is checks.before['displaced']: return (0, 1), ((7, 0, 7, 0), None)
            return actual(s)
        checks.profile = corrupt
    with pytest.raises(AssertionError): checks.arm(checks.before)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('one-port', 'old-counter', 'tag', 'swapped-proposals', 'wrong-dirty', 'reread', 'reset', 'no-read', 'write-ready'))
def test_bad_actual_proposal_or_visibility_precondition_latches_first_error(fault):
    checks, _, _ = fixture(); checks.begin_read_window()
    checks.capture_state(NS(tick=40000), monitored_row(checks, training=True))
    row = monitored_row(checks, proposals=True)
    if fault == 'one-port': row['incoming'][1]['valid'] = 0
    elif fault == 'old-counter': row['incoming'][0]['bits']['counter'] = 0
    elif fault == 'tag': row['incoming'][0]['bits']['tag'] ^= 1
    elif fault == 'swapped-proposals': row['incoming'] = tuple(reversed(row['incoming']))
    elif fault == 'wrong-dirty': row['dirty'] = ((1, 0, 0, 0),) * 2
    elif fault == 'reread': row['reads'][1]['valid'] = 1
    elif fault == 'reset': row['reset'] = 1
    elif fault == 'no-read': row['reads'][0]['valid'] = 0
    else: row['writes'][0]['ready'] = 1
    before = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=40008), row)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    assert checks.pipeline.model.sources.tage.state() == before and checks.coverage.groups['checked'].coverage == 0
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value


@pytest.mark.parametrize('fault', ('not-adjacent', 'wrong-origin', 'wrong-direction', 'disabled', 'missing-input'))
def test_bad_original_feedback_cannot_qualify_the_dual_learning(fault):
    checks, _, _ = held_fixture()
    events = list(checks.accepted); checks.accepted.clear()
    if fault == 'not-adjacent': events[1] = events[1][0] + 2, events[1][1]
    elif fault == 'wrong-origin': events[0] = events[0][0], events[1][1]
    elif fault == 'wrong-direction':
        r = events[0][1]; events[0] = events[0][0], replace(r, branches=(replace(r.branches[0], taken=True), *r.branches[1:]))
    elif fault == 'disabled': checks.pipeline.last_resolution_controls = 40002, (False,) * 7
    else: events = events[:1]
    with pytest.raises(AssertionError): checks.accepted_burst(tuple(events))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('blocked', 'before-proposal', 'old-owner', 'old-counter', 'wrong-tag', 'duplicate'))
def test_retirement_requires_current_owner_and_complete_forwarded_payload(fault):
    checks, program, _ = held_fixture(); old_consumers(checks, program)
    checks.pipeline.last_tick = 40150
    if fault != 'blocked': checks.release()
    transfer = NS(accepted_tick=40160, value=deepcopy(checks.pending_payload[1]))
    if fault == 'before-proposal': transfer.accepted_tick = checks.offered[1]['tick']
    elif fault == 'old-owner': transfer.value = deepcopy(checks.pending_payload[0])
    elif fault == 'old-counter': transfer.value['counter'] = 1
    elif fault == 'wrong-tag': transfer.value['tag'] ^= 1
    elif fault == 'duplicate': checks.write_accepted(1, transfer)
    with pytest.raises(AssertionError): checks.write_accepted(1, transfer)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', tuple((p, n) for p in ('blocked', 'serviced', 'clean') for n in PATHS))
def test_missing_any_declared_consumer_prevents_all_checked_credit(phase, name):
    checks, _ = completed_fixture(); del checks.consumers[phase, name]
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_changed_actual_original_metadata_is_not_rebased_to_the_current_owner():
    checks, _ = completed_fixture(); checks.sources[0].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('count', (-1, 4, True))
def test_no_extra_or_aliased_old_outcome_can_expand_the_declared_counter_program(count):
    with pytest.raises(ValueError): counters_after(count)
