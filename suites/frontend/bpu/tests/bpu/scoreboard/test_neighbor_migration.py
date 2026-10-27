"""Normal semantic events and adversarial observations; no DUT coverage."""
from bpuverify.common.model.configuration import TAGE_ALLOCATION_WAIT
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest

from bpuverify.bpu.checker.neighbor_migration import NeighborMigrationChecks
from bpuverify.bpu.coverage.neighbor_migration import NeighborMigrationCoverage
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS, OUTCOMES, neighbor_preparation, expected_profile
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from bpuverify.bpu.model.pipeline import Redirect
from tests.bpu.scoreboard.test_dual_migration import fixture as migration_fixture, source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def fixture(*, initial_pc=None, checks_type=NeighborMigrationChecks, coverage_type=NeighborMigrationCoverage):
    checks, (model, event, anchor), retired = migration_fixture(initial_pc=initial_pc,
        checks_type=checks_type, coverage_type=coverage_type)
    start_tick=max(32000,1000*len(checks.intents)+1000)
    for index, step in enumerate(checks.neighbor_intents):
        idle = quiet(model, event)
        if event.enabled[3] != step.enabled:
            event = replace(event, enabled=tuple(step.enabled if i == 3 else x for i, x in enumerate(event.enabled)))
            for _ in range(3): model.advance(replace(idle, enabled=event.enabled))
        before = source(model, via(model, event, anchor, checks.history_paths[step.context]), start_tick + 100 * index)
        checks.neighbor_preparing(before, step)
        idle = quiet(model, event); request = resolution(before.token, step.outcomes)
        if step.allocation is not None:
            feedback = model.sources.feedback_for(request)
            for _ in range(TAGE_ALLOCATION_WAIT):
                if model.sources.tage.allocation_at_next_accept(feedback) == step.allocation: break
                model.advance(idle)
            else: raise AssertionError('normal neighbor allocation not eligible')
        model.advance(replace(idle, feedback=request))
        after = source(model, via(model, event, anchor, checks.history_paths[step.context]), start_tick + 40 + 100 * index)
        checks.neighbor_prepared(after, step, (start_tick + 20 + 100 * index, request))
    current_tick = max(34000, start_tick + 100 + 100 * len(checks.neighbor_intents))
    current = {name: source(model, via(model, event, anchor, path), current_tick + 100 * i)
               for i, (name, path) in enumerate(checks.history_paths.items())}
    checks.arm_neighbor(current)
    return checks, (model, event, anchor), retired


def row(checks, *, proposal=None, training=False):
    index = proposal
    count = min(index, checks.service_count) if index is not None else checks.service_count
    return dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        training=dict(valid=int(training), ready=1), prediction=dict(valid=1, ready=1, pc=STREAM_PC),
        incoming=tuple(dict(valid=int(index is not None), bits=deepcopy(payload))
                       for payload in checks.expected_offers[index if index is not None else 0]),
        dirty=((1,) * count + (0,) * (4 - count),) * 2,
        writes=tuple(dict(valid=int(count > 0), ready=0, bits=deepcopy(checks.expected_plan[o][0])) for o in range(2)))


def held_fixture():
    checks, (model, event, anchor), retired = fixture()
    idle = quiet(model, event)
    model.advance(replace(idle, redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    baseline = model.sources.tage.commits
    for s in checks.requests: model.advance(replace(event, feedback=resolution(s.token, OUTCOMES)))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage): break
    else: raise AssertionError('independent pending effects did not mature')
    assert model.sources.tage.commits == baseline
    checks.begin_read_window()
    for i in range(4): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    for i in range(4): checks.capture_state(NS(tick=40008 + 2 * i), row(checks, proposal=i))
    events = tuple((40000 + 2 * i, resolution(s.token, OUTCOMES)) for i, s in enumerate(checks.requests))
    checks.pipeline.last_resolution_controls = 40006, event.enabled
    checks.accepted_burst(events); checks.pending()
    return checks, (model, event, anchor), retired


def blocked_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        middle = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, middle.history, PC, path + 4)
        checks.consume('blocked', name, source(model, token, 40100 + 20 * i))


def serviced_fixture():
    checks, program, retired = held_fixture(); blocked_consumers(checks, program)
    checks.pipeline.last_tick = 40200; checks.release()
    for index in range(2):
        for owner in range(2): checks.write_accepted(owner, NS(accepted_tick=40210 + 2 * index,
            value=deepcopy(checks.expected_plan[owner][index])))
    checks.services_complete()
    quiet(program[0], program[1])
    assert pending_plan(program[0].sources.tage, 7, 0) == ((), ())
    return checks, program, retired


def final_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        checks.consume('serviced', name, source(model, via(model, event, anchor, path), 40300 + 20 * i))


def test_normal_preparation_distinguishes_old_target_current_target_and_independent_neighbor_without_seeds():
    checks, _, _ = fixture()
    assert len(checks.prepared_labels) == 24 and len(checks.neighbor_labels) == 8
    assert len(checks.sources) == 2 and len({id(s.token.history) for s in checks.requests}) == 4
    assert checks.profile(checks.sources[0]) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0)))
    assert checks.profile(checks.before['original']) == ((1, 3), ((7, 1, 1, 0), (7, 0, 4, 0)))
    assert checks.profile(checks.before['neighbor']) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0)))
    assert checks.side_payload[0]['row'] != checks.proposal[0]['row']
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('initial_pc', (PC, PC + 0x40))
def test_neighbor_and_target_geometry_comes_from_owned_history_not_fixed_boot_indices(initial_pc):
    checks, _, _ = fixture(initial_pc=initial_pc)
    assert checks.side_payload[0]['row'] == checks.read(checks.before['neighbor']).rows[3]
    assert checks.proposal[0]['row'] == checks.read(checks.before['original']).rows[3]
    assert checks.side_payload[0]['row'] != checks.proposal[0]['row']


def test_both_pending_results_remain_invisible_until_all_four_services_and_all_six_consumers():
    checks, program, retired = serviced_fixture()
    assert tuple(tuple(p['counter'] for p in plan) for plan in checks.expected_plan) == ((1, 7), (6, 0))
    assert len(checks.consumers) == 3 and not retired
    final_consumers(checks, program)
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    assert len(retired) == len(set(retired)) == 13


@pytest.mark.parametrize('fault', ('reset', 'reread', 'one-port', 'wrong-row', 'wrong-tag', 'old-counter',
    'fresh-uses-old-owner', 'fresh-restores-old-counter', 'overwritten-neighbor', 'short-retention',
    'no-read', 'write-ready', 'not-concurrent', 'proposal-gap', 'proposal-before-input', 'extra-input', 'extra-proposal'))
def test_bad_actual_learning_precondition_or_independent_payload_latches_first_error(fault):
    checks, _, _ = fixture(); checks.begin_read_window()
    for i in range(4): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    checks.capture_state(NS(tick=40008), row(checks, proposal=0))
    actual, tick = row(checks, proposal=1), 40010
    if fault == 'reset': actual['reset'] = 1
    elif fault == 'reread': actual['reads'][1]['valid'] = 1
    elif fault == 'one-port': actual['incoming'][0]['valid'] = 0
    elif fault in ('wrong-row', 'wrong-tag', 'old-counter'):
        actual['incoming'][0]['bits'][{'wrong-row': 'row', 'wrong-tag': 'tag', 'old-counter': 'counter'}[fault]] ^= 1
    elif fault == 'fresh-uses-old-owner': actual['incoming'] = tuple(reversed(actual['incoming']))
    elif fault == 'fresh-restores-old-counter': actual['incoming'][0]['bits']['counter'] = 6
    elif fault == 'overwritten-neighbor':
        checks.capture_state(NS(tick=40010), actual); actual = row(checks, proposal=2); actual['dirty'] = ((1, 0, 0, 0),) * 2; tick = 40012
    elif fault == 'short-retention': actual['dirty'] = ((1, 0, 0),) * 2
    elif fault == 'no-read': actual['reads'][0]['valid'] = 0
    elif fault == 'write-ready': actual['writes'][1]['ready'] = 1
    elif fault == 'not-concurrent': actual = row(checks, training=True); actual['prediction']['valid'] = 0; checks.input_ticks.pop()
    elif fault == 'proposal-gap': tick += 2
    elif fault == 'proposal-before-input': tick = 40000
    elif fault == 'extra-input': actual = row(checks, training=True)
    else:
        for i in range(1, 4): checks.capture_state(NS(tick=40008 + 2 * i), row(checks, proposal=i))
        actual = row(checks, proposal=3); tick = 40020
    state = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=tick), actual)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value and checks.pipeline.model.sources.tage.state() == state
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-input', 'wrong-origin', 'wrong-target', 'wrong-direction', 'input-gap',
    'disabled', 'unobserved-input', 'duplicate-acceptance'))
def test_each_public_input_keeps_the_neighbor_fresh_or_old_source_identity(fault):
    checks, _, _ = held_fixture(); events = list(checks.accepted); checks.accepted.clear()
    if fault == 'missing-input': events.pop()
    elif fault == 'wrong-origin': events[1] = events[1][0], events[0][1]
    elif fault in ('wrong-target', 'wrong-direction'):
        tick, r = events[1]; b = r.branches[0]
        b = replace(b, target=b.target + 2) if fault == 'wrong-target' else replace(b, taken=True)
        events[1] = tick, replace(r, branches=(b, *r.branches[1:]))
    elif fault == 'input-gap': events[-1] = events[-1][0] + 2, events[-1][1]
    elif fault == 'disabled': checks.pipeline.last_resolution_controls = 40006, (False,) * 7
    elif fault == 'unobserved-input': checks.input_ticks.pop()
    else: checks.accepted_burst(tuple(events))
    with pytest.raises(AssertionError): checks.accepted_burst(tuple(events))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-offer', 'overwritten-obligation', 'wrong-neighbor', 'stale-target'))
def test_pending_comparison_requires_both_distinct_logical_results(fault):
    checks, _, _ = held_fixture()
    if fault == 'missing-offer': checks.offered.pop()
    elif fault == 'overwritten-obligation': checks.pipeline.model.sources.tage.cache[7, 0].overflows += 1
    else:
        owner, index = (0, 0) if fault == 'wrong-neighbor' else (0, 1)
        checks.expected_plan[owner][index]['counter'] = 6
    with pytest.raises(AssertionError): checks.pending()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', tuple((p, n) for p in ('blocked', 'serviced') for n in HISTORY_PATHS))
def test_missing_any_required_history_visibility_consumer_prevents_checked(phase, name):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    del checks.consumers[phase, name]
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-neighbor-before-release', 'early', 'wrong-owner', 'wrong-row', 'wrong-tag',
    'stale-counter', 'invalid-entry', 'target-before-neighbor', 'extra-service', 'service-gap', 'unpaired-service'))
def test_actual_sdk_services_keep_both_complete_identities_and_their_current_owners(fault):
    checks, program, _ = held_fixture(); blocked_consumers(checks, program)
    if fault == 'missing-neighbor-before-release':
        del checks.consumers['blocked', 'neighbor']
        with pytest.raises(AssertionError): checks.release()
        return
    checks.pipeline.last_tick = 40200; checks.release()
    owner, tick, payload = 0, 40210, deepcopy(checks.expected_plan[0][0])
    if fault == 'early': tick = 40200
    elif fault == 'wrong-owner': owner = 1
    elif fault in ('wrong-row', 'wrong-tag'): payload[fault[6:]] ^= 1
    elif fault == 'stale-counter': payload['counter'] = 2
    elif fault == 'invalid-entry': payload['valid'] = 0
    elif fault == 'target-before-neighbor': payload = deepcopy(checks.expected_plan[0][1])
    elif fault == 'extra-service':
        for i in range(2): checks.write_accepted(0, NS(accepted_tick=40210 + i * 2, value=deepcopy(checks.expected_plan[0][i])))
    elif fault == 'service-gap':
        checks.write_accepted(0, NS(accepted_tick=tick, value=payload)); tick += 4; payload = deepcopy(checks.expected_plan[0][1])
    elif fault == 'unpaired-service':
        for i in range(2):
            for o in range(2): checks.write_accepted(o, NS(accepted_tick=40210 + i * 2 + o * 2,
                value=deepcopy(checks.expected_plan[o][i])))
        with pytest.raises(AssertionError): checks.services_complete()
        return
    with pytest.raises(AssertionError): checks.write_accepted(owner, NS(accepted_tick=tick, value=payload))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('owner,index', tuple((o, i) for o in range(2) for i in range(2)))
def test_missing_any_one_of_four_actual_services_cannot_close(owner, index):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    checks.phase = 'service'; del checks.written[owner][index]
    with pytest.raises(AssertionError): checks.services_complete()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('actual-input-mutated', 'owned-input-mutated', 'repeated-finish'))
def test_all_four_snapshots_are_preserved_and_checked_credit_is_single_use(fault):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    if fault == 'actual-input-mutated': checks.requests[0].meta.resolve['sequence'] ^= 1
    elif fault == 'owned-input-mutated': checks.input_defined[0]['bad'] = 1
    else: checks.finish()
    with pytest.raises(AssertionError): checks.finish()


@pytest.mark.parametrize('name,serviced', (('other', False), ('original', 1), ('neighbor', None)))
def test_unknown_history_or_visibility_is_not_a_new_functional_bin(name, serviced):
    with pytest.raises(ValueError): expected_profile(name, serviced=serviced)


def test_case_expresses_intent_without_raw_io_or_a_private_scheduler():
    for path in ('bpuverify/bpu/case/neighbor_migration.py', 'tests/bpu/testcase/test_neighbor_migration.py'):
        for node in ast.walk(ast.parse(Path(path).read_text())):
            assert not isinstance(node, (ast.Assert, ast.ClassDef))
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', None)
                assert name not in {'ClockCycles', 'RisingEdge', 'FallingEdge', 'set_', 'get_', 'gather', 'create_task', 'Scoreboard'}
