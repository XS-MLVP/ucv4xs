"""Independent full-hit event program and bad receipts; no DUT coverage credit."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest

from bpuverify.bpu.checker.full_neighbor_migration import FullNeighborMigrationChecks
from bpuverify.bpu.coverage.full_neighbor_migration import FullNeighborMigrationCoverage
from bpuverify.bpu.model.tage.full_neighbor_migration import PC, HISTORY_PATHS, NEIGHBOR_NAMES, OUTCOMES
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from bpuverify.bpu.model.pipeline import Redirect
from tests.bpu.scoreboard.test_neighbor_migration import fixture as neighbor_fixture, row
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def fixture(*, initial_pc=None):
    return neighbor_fixture(initial_pc=initial_pc, checks_type=FullNeighborMigrationChecks,
                            coverage_type=FullNeighborMigrationCoverage)


def held_fixture():
    checks, (model, event, anchor), retired = fixture()
    idle = quiet(model, event)
    model.advance(replace(idle, redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    baseline = model.sources.tage.commits
    for s in checks.requests:
        r = resolution(s.token, OUTCOMES)
        assert not model.sources.feedback_for(r).reread
        model.advance(replace(event, feedback=r))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage): break
    else: raise AssertionError('full-hit learning did not mature')
    assert model.sources.tage.commits == baseline
    checks.begin_read_window()
    for i in range(checks.input_count): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    for i in range(checks.input_count): checks.capture_state(NS(tick=40012 + 2 * i), row(checks, proposal=i))
    checks.pipeline.last_resolution_controls = 40010, event.enabled
    events = tuple((40000 + 2 * i, resolution(s.token, OUTCOMES)) for i, s in enumerate(checks.requests))
    checks.accepted_burst(events); checks.pending()
    return checks, (model, event, anchor), retired, baseline


def blocked_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        middle = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, middle.history, PC, path + 4)
        checks.consume('blocked', name, source(model, token, 40300 + 20 * i))


def serviced_fixture():
    checks, program, retired, baseline = held_fixture(); blocked_consumers(checks, program)
    checks.pipeline.last_tick = 40400; checks.release()
    for i in range(checks.service_count):
        for owner in range(2): checks.write_accepted(owner, NS(accepted_tick=40410 + 2 * i,
            value=deepcopy(checks.expected_plan[owner][i])))
    checks.services_complete(); quiet(program[0], program[1])
    assert program[0].sources.tage.commits == baseline + 8 and pending_plan(program[0].sources.tage, 7, 0) == ((), ())
    return checks, program, retired


def final_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        checks.consume('serviced', name, source(model, via(model, event, anchor, path), 40500 + 20 * i))


def test_full_program_uses_52_normal_steps_six_real_sources_and_four_independent_results():
    checks, _, _ = fixture()
    assert len(checks.prepared_labels) == 24 and len(checks.neighbor_labels) == 28
    assert checks.input_count == len(checks.requests) == len({id(s.token.history) for s in checks.requests}) == 6
    assert checks.service_count == 4 and len(checks.before) == 5
    assert len({checks.read(checks.before[n]).rows[3] for n in (*NEIGHBOR_NAMES, 'original')}) == 4
    assert all(checks.profile(checks.before[n]) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0))) for n in NEIGHBOR_NAMES)
    assert checks.profile(checks.before['original']) == ((1, 3), ((7, 1, 1, 0), (7, 0, 4, 0)))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('initial_pc', (PC, PC + 0x40))
def test_full_program_derives_every_history_coordinate_from_its_owned_boot(initial_pc):
    checks, _, _ = fixture(initial_pc=initial_pc)
    for name in NEIGHBOR_NAMES:
        assert checks.side_payloads[name][0]['row'] == checks.read(checks.before[name]).rows[3]
    assert len({checks.read(checks.before[n]).rows[3] for n in (*NEIGHBOR_NAMES, 'original')}) == 4


def test_full_hits_preserve_all_eight_effects_until_eight_services_and_ten_consumers_close():
    checks, program, retired = serviced_fixture()
    assert tuple(tuple(p['counter'] for p in owner) for owner in checks.expected_plan) == ((1, 1, 1, 7), (6, 6, 6, 0))
    assert [h['index'] for h in checks.full_hits] == [4, 5]
    assert all(h['dirty'] == ((1, 1, 1, 1),) * 2 for h in checks.full_hits)
    assert checks.coverage.groups['checked'].coverage == 0 and not retired
    final_consumers(checks, program); checks.finish()
    assert len(retired) == len(set(retired)) == 19
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())


@pytest.mark.parametrize('fault', ('not-full-first', 'not-full-second', 'one-owner-not-full', 'short-full-vector',
    'wrong-row', 'wrong-tag', 'old-counter', 'swapped-owners', 'read-gap', 'service-ready', 'extra-proposal'))
def test_each_actual_full_hit_prestate_and_complete_old_proposal_are_mandatory(fault):
    checks, _, _ = fixture(); checks.begin_read_window()
    for i in range(6): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    count = 5 if fault == 'not-full-second' else 4
    for i in range(count): checks.capture_state(NS(tick=40012 + 2 * i), row(checks, proposal=i))
    actual = row(checks, proposal=count); tick = 40012 + count * 2
    if fault in ('not-full-first', 'not-full-second'): actual['dirty'] = ((1, 1, 1, 0),) * 2
    elif fault == 'one-owner-not-full': actual['dirty'] = ((1, 1, 1, 1), (1, 1, 0, 1))
    elif fault == 'short-full-vector': actual['dirty'] = ((1, 1, 1),) * 2
    elif fault in ('wrong-row', 'wrong-tag', 'old-counter'):
        actual['incoming'][0]['bits'][{'wrong-row': 'row', 'wrong-tag': 'tag', 'old-counter': 'counter'}[fault]] ^= 1
    elif fault == 'swapped-owners': actual['incoming'] = tuple(reversed(actual['incoming']))
    elif fault == 'read-gap': actual['reads'][0]['valid'] = 0
    elif fault == 'service-ready': actual['writes'][0]['ready'] = 1
    else:
        checks.capture_state(NS(tick=40020), row(checks, proposal=4))
        checks.capture_state(NS(tick=40022), row(checks, proposal=5)); tick = 40024
    state = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=tick), actual)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value and checks.pipeline.model.sources.tage.state() == state
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-full-first', 'missing-full-second', 'wrong-source-index', 'wrong-full-tick',
    'missing-sixth-offer', 'lost-neighbor', 'target-stale', 'reference-overflow'))
def test_pending_needs_both_full_witnesses_and_every_independently_derived_result(fault):
    checks, _, _, _ = held_fixture()
    if fault == 'missing-full-first': checks.full_hits.pop(0)
    elif fault == 'missing-full-second': checks.full_hits.pop()
    elif fault == 'wrong-source-index': checks.full_hits[0]['index'] = 3
    elif fault == 'wrong-full-tick': checks.full_hits[-1]['tick'] += 2
    elif fault == 'missing-sixth-offer': checks.offered.pop()
    elif fault == 'lost-neighbor': checks.expected_plan[0][1]['counter'] = 2
    elif fault == 'target-stale': checks.expected_plan[0][-1]['counter'] = 6
    else: checks.pipeline.model.sources.tage.cache[7, 0].overflows += 1
    with pytest.raises(AssertionError) as first: checks.pending()
    with pytest.raises(AssertionError) as second: checks.raise_failure()
    assert first.value is second.value
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-source', 'neighbor-alias', 'fresh-alias', 'old-alias', 'wrong-target', 'wrong-direction',
    'input-gap', 'disabled', 'unobserved-input', 'duplicate-acceptance'))
def test_all_six_public_receipts_own_their_exact_history_not_only_the_same_pc(fault):
    checks, _, _, _ = held_fixture(); events = list(checks.accepted); checks.accepted.clear()
    if fault == 'missing-source': events.pop()
    elif fault in ('neighbor-alias', 'fresh-alias', 'old-alias'):
        index = {'neighbor-alias': 1, 'fresh-alias': 3, 'old-alias': 5}[fault]
        events[index] = events[index][0], events[0][1]
    elif fault in ('wrong-target', 'wrong-direction'):
        tick, r = events[-1]; b = r.branches[0]
        b = replace(b, target=b.target + 2) if fault == 'wrong-target' else replace(b, taken=True)
        events[-1] = tick, replace(r, branches=(b, *r.branches[1:]))
    elif fault == 'input-gap': events[-1] = events[-1][0] + 2, events[-1][1]
    elif fault == 'disabled': checks.pipeline.last_resolution_controls = 40010, (False,) * 7
    elif fault == 'unobserved-input': checks.input_ticks.pop()
    else: checks.accepted_burst(tuple(events))
    with pytest.raises(AssertionError): checks.accepted_burst(tuple(events))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('owner,index', tuple((o, i) for o in range(2) for i in range(4)))
def test_missing_any_of_eight_actual_services_prevents_full_result_closure(owner, index):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    checks.phase = 'service'; del checks.written[owner][index]
    with pytest.raises(AssertionError): checks.services_complete()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', tuple((p, n) for p in ('blocked', 'serviced') for n in HISTORY_PATHS))
def test_missing_any_of_ten_required_consumers_cannot_credit_checked(phase, name):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    del checks.consumers[phase, name]
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('before-release', 'wrong-owner', 'wrong-neighbor', 'stale-counter', 'wrong-tag',
    'target-before-neighbors', 'lost-target-update', 'extra-service', 'unpaired-retirement'))
def test_full_sdk_service_cannot_substitute_a_neighbor_or_just_match_the_final_direction(fault):
    checks, program, _, _ = held_fixture(); blocked_consumers(checks, program)
    checks.pipeline.last_tick = 40400; checks.release()
    owner, tick, payload = 0, 40410, deepcopy(checks.expected_plan[0][0])
    if fault == 'before-release': tick = 40400
    elif fault == 'wrong-owner': owner = 1
    elif fault == 'wrong-neighbor': payload = deepcopy(checks.expected_plan[0][1])
    elif fault == 'stale-counter': payload['counter'] = 2
    elif fault == 'wrong-tag': payload['tag'] ^= 1
    elif fault == 'target-before-neighbors': payload = deepcopy(checks.expected_plan[0][-1])
    elif fault == 'lost-target-update':
        for i in range(3): checks.write_accepted(0, NS(accepted_tick=40410 + 2 * i, value=deepcopy(checks.expected_plan[0][i])))
        tick = 40416; payload = deepcopy(checks.expected_plan[0][-1]); payload['counter'] = 6
    elif fault == 'extra-service':
        for i in range(4): checks.write_accepted(0, NS(accepted_tick=40410 + 2 * i, value=deepcopy(checks.expected_plan[0][i])))
    else:
        for i in range(4):
            for o in range(2): checks.write_accepted(o, NS(accepted_tick=40410 + i * 2 + o * 2,
                value=deepcopy(checks.expected_plan[o][i])))
        with pytest.raises(AssertionError): checks.services_complete()
        return
    with pytest.raises(AssertionError): checks.write_accepted(owner, NS(accepted_tick=tick, value=payload))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('index', range(6))
def test_each_actual_input_snapshot_survives_full_capacity_learning(index):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    checks.requests[index].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_full_case_has_no_raw_io_edges_or_private_scheduler():
    for path in ('bpuverify/bpu/case/full_neighbor_migration.py', 'tests/bpu/testcase/test_full_neighbor_migration.py'):
        for node in ast.walk(ast.parse(Path(path).read_text())):
            assert not isinstance(node, (ast.Assert, ast.ClassDef))
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', None)
                assert name not in {'ClockCycles', 'RisingEdge', 'FallingEdge', 'set_', 'get_', 'gather', 'create_task', 'Scoreboard'}
