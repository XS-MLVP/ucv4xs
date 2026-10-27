"""Independent normal-event lifecycle and adversarial receipts, never a DUT."""
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest
from toffee import Transfer, XEvent, XEventKind, XPhase
from bpuverify.bpu.checker.partial_reuse import PartialReuseChecks
from bpuverify.bpu.coverage.partial_reuse import PartialReuseCoverage
from bpuverify.bpu.model.tage.partial_reuse import PC, HISTORY_PATHS, NEIGHBOR_NAMES, OUTCOMES
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from bpuverify.bpu.model.pipeline import Redirect
from tests.bpu.scoreboard.test_neighbor_migration import fixture as prepare_fixture
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def fixture(*, initial_pc=None):
    return prepare_fixture(initial_pc=initial_pc, checks_type=PartialReuseChecks, coverage_type=PartialReuseCoverage)


def row(checks, *, dirty=4, training=False, proposal=None):
    return dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        training=dict(valid=int(training), ready=1), prediction=dict(valid=1, ready=1, pc=STREAM_PC),
        dirty=((1,) * dirty + (0,) * (4 - dirty),) * 2,
        incoming=tuple(dict(valid=int(proposal is not None), bits=deepcopy(p))
                       for p in checks.expected_offers[0 if proposal is None else proposal]),
        writes=tuple(dict(valid=1, ready=0, bits=deepcopy(checks.complete_plan[o][0])) for o in range(2)))


def transfer(tick, payload):
    return Transfer(XEvent(event_id=tick, tick=tick, phase=XPhase.RISING_STABLE, kind=XEventKind.CLOCK_RISE), deepcopy(payload))


def candidate(checks, tick=40019):
    actual = row(checks)
    actual['reads'][0]['valid'] = 0
    for p in actual['writes']: p['ready'] = 1
    event = XEvent(event_id=tick, tick=tick, phase=XPhase.DRIVE_STABLE, kind=XEventKind.DRIVE_STABLE)
    return event, actual


def prepare_pair(checks):
    event, actual = candidate(checks)
    checks.prepare_partial(event, actual)


def model_burst(checks, model, event, start, stop):
    for s in checks.requests[start:stop]:
        r = resolution(s.token, OUTCOMES)
        assert not model.sources.feedback_for(r).reread
        model.advance(replace(event, feedback=r))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage): return
    raise AssertionError('independent feedback did not mature')


def held_fixture():
    checks, (model, event, anchor), retired = fixture()
    idle = quiet(model, event)
    model.advance(replace(idle, redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    baseline = model.sources.tage.commits
    model_burst(checks, model, event, 0, 4)
    assert model.sources.tage.commits == baseline
    checks.begin_read_window()
    for i in range(4): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, dirty=0, training=True))
    for i in range(4): checks.capture_state(NS(tick=40008 + 2 * i), row(checks, dirty=i, proposal=i))
    checks.capture_state(NS(tick=40016), row(checks))
    checks.pipeline.last_resolution_controls = 40006, event.enabled
    events = tuple((40000 + 2 * i, resolution(s.token, OUTCOMES)) for i, s in enumerate(checks.requests[:4]))
    checks.accepted_burst(events); checks.pending()
    return checks, (model, event, anchor), retired, baseline


def partial_fixture():
    checks, (model, event, anchor), retired, baseline = held_fixture()
    checks.pipeline.last_tick = 40018
    receipt = Future(); checks.begin_partial(receipt, Future())
    model.advance(replace(event, prediction_ready=False))
    assert model.sources.tage.commits == baseline + 2
    for _ in range(8): model.advance(event)
    assert model.sources.tage.commits == baseline + 2
    prepare_pair(checks)
    for owner in range(2): checks.write_accepted(owner, transfer(40020, checks.complete_plan[owner][0]))
    checks.capture_state(NS(tick=40022), row(checks, dirty=3))
    checks.pipeline.last_tick = 40022; checks.partial_complete(receipt.result())
    return checks, (model, event, anchor), retired, baseline


def refill_fixture():
    checks, (model, event, anchor), retired, baseline = partial_fixture()
    model_burst(checks, model, event, 4, 7)
    assert model.sources.tage.commits == baseline + 2
    for i in range(3): checks.capture_state(NS(tick=40100 + 2 * i), row(checks, dirty=3, training=True))
    for i in range(3): checks.capture_state(NS(tick=40106 + 2 * i), row(checks, dirty=3 if i == 0 else 4, proposal=i + 4))
    checks.capture_state(NS(tick=40112), row(checks))
    checks.pipeline.last_resolution_controls = 40104, event.enabled
    events = tuple((40100 + 2 * i, resolution(s.token, OUTCOMES)) for i, s in enumerate(checks.requests[4:]))
    checks.accepted_burst(events); checks.pending()
    return checks, (model, event, anchor), retired, baseline


def blocked_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        middle = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, middle.history, PC, path + 4)
        checks.consume('blocked', name, source(model, token, 40200 + 20 * i))


def serviced_fixture():
    checks, program, retired, baseline = refill_fixture(); blocked_consumers(checks, program)
    checks.pipeline.last_tick = 40400; checks.release()
    for i in range(1, 5):
        for owner in range(2): checks.write_accepted(owner, transfer(40410 + 2 * (i - 1), checks.complete_plan[owner][i]))
    checks.services_complete(); quiet(program[0], program[1])
    assert program[0].sources.tage.commits == baseline + 10 and pending_plan(program[0].sources.tage, 3, 0) == ((), ())
    return checks, program, retired


def final_consumers(checks, program):
    model, event, anchor = program
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        checks.consume('serviced', name, source(model, via(model, event, anchor, path), 40500 + 20 * i))


def test_62_normal_steps_save_seven_sources_for_five_independent_histories():
    checks, _, _ = fixture()
    assert len(checks.prepared_labels) + len(checks.neighbor_labels) == 62
    assert len(checks.requests) == len({id(s.token.history) for s in checks.requests}) == 7
    assert len({checks.read(checks.before[n]).rows[3] for n in (*NEIGHBOR_NAMES, 'original')}) == 5
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('initial_pc', (PC, PC + 0x40))
def test_reused_identity_coordinates_follow_owned_history_not_a_fixed_boot(initial_pc):
    checks, _, _ = fixture(initial_pc=initial_pc)
    assert checks.side_payloads['neighbor-fourth'][0]['row'] == checks.read(checks.before['neighbor-fourth']).rows[3]


def test_all_ten_rules_need_partial_pair_refill_ten_services_twelve_consumers_and_snapshots():
    checks, program, retired = serviced_fixture()
    assert len(checks.offered) == 7 and len(checks.full_hits) == 2
    assert len(checks.consumers) == 6 and not retired
    assert tuple(tuple(p['counter'] for p in owner) for owner in checks.final_plan) == ((1, 1, 1, 7), (6, 6, 6, 0))
    assert checks.coverage.groups['checked'].coverage == 0
    final_consumers(checks, program); checks.finish()
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())
    assert len(retired) == len(set(retired)) == 22


@pytest.mark.parametrize('fault', ('missing-proposal', 'missing-acceptance', 'not-full', 'premature-service', 'reference-overflow'))
def test_initial_full_set_is_mandatory_before_partial_release(fault):
    checks, _, _, _ = held_fixture()
    if fault == 'missing-proposal': checks.offered.pop()
    elif fault == 'missing-acceptance': checks.accepted.pop()
    elif fault == 'not-full': checks.last[1]['dirty'] = ((1, 1, 1, 0),) * 2
    elif fault == 'premature-service': checks.written[0].append((40017, checks.complete_plan[0][0]))
    else: checks.pipeline.model.sources.tage.cache[3, 0].overflows += 1
    with pytest.raises(AssertionError) as first: checks.pending()
    with pytest.raises(AssertionError) as second: checks.raise_failure()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-owner', 'unpaired', 'not-resumed', 'lost-pending', 'not-three', 'wrong-receipt', 'stale-receipt',
                                  'missing-preparation', 'wrong-preparation-tick'))
def test_partial_boundary_needs_exactly_one_compared_pair_and_restored_reads(fault):
    checks, _, _, _ = partial_fixture(); checks.phase = 'partial-service'
    event = checks.partial_event
    if fault == 'missing-owner': checks.written[1].clear()
    elif fault == 'unpaired': checks.written[1][0] = event.tick + 2, checks.written[1][0][1]
    elif fault == 'not-resumed': checks.last[1]['reads'][0]['valid'] = 0
    elif fault == 'lost-pending': checks.initial_plan[0][1]['counter'] ^= 1
    elif fault == 'not-three': checks.last[1]['dirty'] = ((1, 1, 0, 0),) * 2
    elif fault == 'wrong-receipt': event = replace(event, tick=event.tick + 2)
    elif fault == 'stale-receipt': checks.partial_receipt = Future()
    elif fault == 'missing-preparation': checks.partial_candidate = None
    else: checks.partial_candidate['tick'] -= 2
    with pytest.raises(AssertionError): checks.partial_complete(event)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('extra-service', 'wrong-payload', 'early-service', 'external-event', 'wrong-owner'))
def test_partial_window_cannot_silently_service_a_second_identity(fault):
    checks, _, _, _ = held_fixture(); checks.pipeline.last_tick = 40018; checks.begin_partial(Future(), Future()); prepare_pair(checks)
    owner, actual = 0, transfer(40020, checks.complete_plan[0][0])
    if fault == 'extra-service': checks.write_accepted(owner, actual); actual = transfer(40022, checks.complete_plan[0][1])
    elif fault == 'wrong-payload': actual.value['counter'] ^= 1
    elif fault == 'early-service': actual = transfer(40018, actual.value)
    elif fault == 'external-event': actual = Transfer(replace(actual.event, phase=XPhase.EXTERNAL), actual.value)
    else: owner = 2
    with pytest.raises(AssertionError): checks.write_accepted(owner, actual)
    assert not checks.partial_receipt.done() and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('wrong-phase', 'wrong-payload', 'not-full', 'competing-read', 'duplicate-preparation', 'early-preparation'))
def test_candidate_only_schedules_control_and_never_counts_as_service(fault):
    checks, _, _, _ = held_fixture(); checks.pipeline.last_tick = 40018
    checks.begin_partial(Future(), Future())
    event, actual = candidate(checks)
    if fault == 'wrong-phase': event = replace(event, phase=XPhase.RISING_STABLE)
    elif fault == 'wrong-payload': actual['writes'][0]['bits']['tag'] ^= 1
    elif fault == 'not-full': actual['dirty'] = ((1, 1, 1, 0),) * 2
    elif fault == 'competing-read': actual['reads'][0]['valid'] = 1
    elif fault == 'duplicate-preparation': checks.prepare_partial(event, actual)
    else: event = replace(event, tick=40017)
    with pytest.raises(AssertionError): checks.prepare_partial(event, actual)
    assert not checks.partial_receipt.done() and tuple(map(len, checks.written.values())) == (0, 0)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('not-released', 'not-full-first-old', 'not-full-second-old', 'wrong-new-tag', 'inherited-old-counter',
    'wrong-old-owner', 'read-gap', 'reread', 'reset', 'not-concurrent', 'missing-half', 'proposal-gap', 'extra-proposal'))
def test_actual_refill_proposals_prove_released_capacity_and_own_original_identity(fault):
    checks, _, _, _ = partial_fixture()
    for i in range(3): checks.capture_state(NS(tick=40100 + 2 * i), row(checks, dirty=3, training=True))
    index = 4
    if fault in ('not-full-first-old', 'not-full-second-old', 'wrong-old-owner', 'proposal-gap'):
        checks.capture_state(NS(tick=40106), row(checks, dirty=3, proposal=4)); index = 5
    if fault == 'not-full-second-old':
        checks.capture_state(NS(tick=40108), row(checks, proposal=5)); index = 6
    actual = row(checks, dirty=3 if index == 4 else 4, proposal=index); tick = 40106 + 2 * (index - 4)
    if fault == 'not-released': actual['dirty'] = ((1, 1, 1, 1),) * 2
    elif fault in ('not-full-first-old', 'not-full-second-old'): actual['dirty'] = ((1, 1, 1, 0),) * 2
    elif fault == 'wrong-new-tag': actual['incoming'][0]['bits']['tag'] ^= 1
    elif fault == 'inherited-old-counter': actual['incoming'][0]['bits']['counter'] = 0
    elif fault == 'wrong-old-owner': actual['incoming'] = tuple(reversed(actual['incoming']))
    elif fault == 'read-gap': actual['reads'][0]['valid'] = 0
    elif fault == 'reread': actual['reads'][1]['valid'] = 1
    elif fault == 'reset': actual['reset'] = 1
    elif fault == 'not-concurrent': actual = row(checks, training=True); actual['prediction']['valid'] = 0; checks.input_ticks.pop()
    elif fault == 'missing-half': actual['incoming'][1]['valid'] = 0
    elif fault == 'proposal-gap': tick += 2
    else:
        for i in range(4, 7): checks.capture_state(NS(tick=40106 + 2 * (i - 4)), row(checks, dirty=3 if i == 4 else 4, proposal=i))
        tick = 40112
    checks.capture_state(NS(tick=tick), actual)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-offer', 'missing-full-hit', 'wrong-full-index', 'wrong-full-tick', 'lost-neighbor', 'stale-target', 'overflow'))
def test_refill_comparison_requires_all_pending_results_and_two_actual_full_hits(fault):
    checks, _, _, _ = refill_fixture()
    if fault == 'missing-offer': checks.offered.pop()
    elif fault == 'missing-full-hit': checks.full_hits.pop()
    elif fault == 'wrong-full-index': checks.full_hits[0]['index'] = 4
    elif fault == 'wrong-full-tick': checks.full_hits[0]['tick'] += 2
    elif fault == 'lost-neighbor': checks.final_plan[0][1]['counter'] ^= 1
    elif fault == 'stale-target': checks.final_plan[0][-1]['counter'] = 6
    else: checks.pipeline.model.sources.tage.cache[3, 0].overflows += 1
    with pytest.raises(AssertionError): checks.pending()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('start', (0, 4))
@pytest.mark.parametrize('fault', ('missing-source', 'wrong-source', 'input-gap', 'disabled', 'unobserved', 'duplicate'))
def test_each_burst_owns_its_exact_public_sources(start, fault):
    checks, _, _, _ = held_fixture() if start == 0 else refill_fixture()
    events = list(checks.accepted[start:]); del checks.accepted[start:]
    if fault == 'missing-source': events.pop()
    elif fault == 'wrong-source': events[-1] = events[-1][0], events[0][1]
    elif fault == 'input-gap': events[-1] = events[-1][0] + 2, events[-1][1]
    elif fault == 'disabled': checks.pipeline.last_resolution_controls = events[-1][0], (False,) * 7
    elif fault == 'unobserved': checks.input_ticks.pop()
    else: checks.accepted_burst(tuple(events))
    with pytest.raises(AssertionError): checks.accepted_burst(tuple(events))


@pytest.mark.parametrize('owner,index', tuple((o, i) for o in range(2) for i in range(5)))
def test_missing_any_of_ten_complete_services_prevents_closure(owner, index):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    checks.phase = 'service'; del checks.written[owner][index]
    with pytest.raises(AssertionError): checks.services_complete()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('wrong-row', 'wrong-tag', 'wrong-counter', 'invalid-entry', 'neighbor-order',
                                  'repeat-serviced-neighbor', 'wrong-owner', 'service-gap', 'unpaired'))
def test_final_service_cannot_hide_identity_or_timing_loss_by_matching_the_last_counter(fault):
    checks, program, _, _ = refill_fixture(); blocked_consumers(checks, program)
    checks.pipeline.last_tick = 40400; checks.release()
    owner, actual = 0, transfer(40410, checks.complete_plan[0][1])
    if fault in ('wrong-row', 'wrong-tag', 'wrong-counter', 'invalid-entry'):
        key = {'wrong-row':'row', 'wrong-tag':'tag', 'wrong-counter':'counter', 'invalid-entry':'valid'}[fault]
        actual.value[key] ^= 1
    elif fault == 'neighbor-order': actual = transfer(40410, checks.complete_plan[0][2])
    elif fault == 'repeat-serviced-neighbor': actual = transfer(40410, checks.complete_plan[0][0])
    elif fault == 'wrong-owner': owner = 1
    elif fault == 'service-gap':
        checks.write_accepted(0, actual); actual = transfer(40414, checks.complete_plan[0][2])
    else:
        for i in range(1, 5):
            for o in range(2): checks.write_accepted(o, transfer(40410 + 2 * (i - 1) + 2 * o, checks.complete_plan[o][i]))
        with pytest.raises(AssertionError): checks.services_complete()
        return
    with pytest.raises(AssertionError): checks.write_accepted(owner, actual)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('phase,name', tuple((p, n) for p in ('blocked', 'serviced') for n in HISTORY_PATHS))
def test_missing_any_of_twelve_distinguishable_consumers_prevents_checked(phase, name):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    del checks.consumers[phase, name]
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('index', range(7))
def test_every_original_input_snapshot_is_immutable(index):
    checks, program, _ = serviced_fixture(); final_consumers(checks, program)
    checks.requests[index].meta.resolve['sequence'] ^= 1
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_case_has_no_raw_io_clock_wait_or_private_async_scheduler():
    for path in ('bpuverify/bpu/case/partial_reuse.py', 'tests/bpu/testcase/test_partial_reuse.py'):
        for node in ast.walk(ast.parse(Path(path).read_text())):
            assert not isinstance(node, (ast.Assert, ast.ClassDef))
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', None)
                assert name not in {'ClockCycles', 'RisingEdge', 'FallingEdge', 'set_', 'get_', 'gather', 'create_task', 'Scoreboard'}
