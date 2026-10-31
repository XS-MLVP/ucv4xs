"""Independent versions and adversarial actual packets, never DUT credit."""
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard, Transfer, XEvent, XEventKind, XPhase
from suites.frontend.bpu.bpu.checker.service_relearning import Checks
from suites.frontend.bpu.bpu.coverage.service_relearning import Coverage, RULES
from suites.frontend.bpu.bpu.model.pipeline import Outcome, Resolution, Redirect
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.bpu.model.tage.forwarding import PC, resolved_path
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC, STREAM_POSITION, VIA_PC, pending_plan, learning_inflight
from suites.frontend.bpu.bpu.model.tage.service_relearning import PROGRAMS, Program
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import two_history_program, streaming_query, counters
from tests.bpu.scoreboard.test_direction_sources import quiet, revisit


@lru_cache(maxsize=1)
def foundation(): return two_history_program()


def consumers(model, event, anchor):
    first = streaming_query(model, event, anchor.history, PC, anchor.pc+4)
    middle = streaming_query(model, event, anchor.history, VIA_PC, anchor.pc+4)
    second = streaming_query(model, event, middle.history, PC, VIA_PC+4)
    return first, second


def initial_reference(program):
    model, event, anchor, originals = deepcopy(foundation())
    sources = tuple(originals[i] for i in (*program.first_order, 2))
    loop = revisit(model, event, anchor, STREAM_PC)
    idle = quiet(model, event)
    model.advance(replace(idle, feedback=Resolution(loop.history, loop.pc,
        (Outcome(STREAM_POSITION, STREAM_PC, Kind.DIRECT, True, mispredict=True),), origin=loop)))
    quiet(model, event)
    model.advance(replace(event, redirect=Redirect(anchor.history, anchor.pc+4, STREAM_PC, True)))
    for _ in range(8): model.advance(event)
    baseline = model.sources.tage.commits
    for source in sources[:2]: model.advance(replace(event, feedback=resolution(source, resolved_path())))
    for _ in range(32):
        model.advance(event)
        if not learning_inflight(model.sources.tage): break
    else: raise AssertionError('first independent learning did not mature')
    assert model.sources.tage.commits == baseline
    assert tuple(tuple(p['counter'] for p in v) for v in pending_plan(model.sources.tage, 7, PC%4)) == ((1, 1), (6, 6))
    old = consumers(model, event, anchor)
    assert all(counters(model.sources.snapshot(s).read) == (2, 5) for s in old)
    return model, event, anchor, sources, old, baseline


def source(token, tick):
    return NS(token=token, prediction_tick=tick, meta_tick=tick+4, meta={'original': tick})


def packet(checks, *, proposal=None, remaining=False, ready=False, drained=False):
    plan = checks.wanted_plan(remaining=remaining)
    records, dirty = [], []
    for owner in range(2):
        retained, marks = [], []
        for history in range(2):
            payload = dict(checks.payloads[history][owner], counter=(
                checks.profile.target[owner] if remaining and history == 0 else (1, 6)[owner]))
            retained.append(dict(shadow=1, **payload))
            marks.append(int(not drained and any(p['row'] == payload['row'] for p in plan[owner])))
        records.append(tuple(retained + [dict(shadow=0, row=0, valid=0, tag=0, counter=0) for _ in range(2)]))
        dirty.append(tuple(marks+[0, 0]))
    incoming = tuple(dict(valid=int(proposal is not None and (proposal < 2 or checks.profile.late_flags[o])),
        bits=deepcopy(checks.payloads[0 if proposal is None else checks.program.feedback_order[proposal]][o])) for o in range(2))
    row = dict(reset=0, reads=({'valid': int(not ready), 'mask': 1}, {'valid': 0, 'mask': 0}),
        prediction=dict(valid=1, ready=1, pc=STREAM_PC), training=dict(valid=0, ready=1),
        dirty=tuple(dirty), incoming=incoming,
        writes=tuple(dict(valid=int(not drained and bool(v)), ready=int(ready), bits=deepcopy(v[0] if v else {})) for v in plan))
    return dict(state=row, records=tuple(records))


def rising(tick): return XEvent(event_id=tick, tick=tick, phase=XPhase.RISING_STABLE, kind=XEventKind.CLOCK_RISE)
def preparation(tick): return XEvent(event_id=tick, tick=tick, phase=XPhase.DRIVE_STABLE, kind=XEventKind.DRIVE_STABLE)


def held(program):
    model, event, anchor, tokens, old, baseline = initial_reference(program)
    retired = []
    pipeline = NS(board=Scoreboard('service-relearning-contract'), model=model, last_tick=1040,
        source_token=lambda s:s.token, raise_failure=lambda:None, retire_source=retired.append,
        corrections_for_source=lambda s:((s.prediction_tick+2, 2),))
    checks = Checks(pipeline, Coverage(program), program)
    checks.arm(tuple(source(t, 100+10*i) for i, t in enumerate(tokens)))
    checks.begin_read_window()
    for i in range(2):
        actual = packet(checks); actual['state']['training']['valid'] = 1
        checks.capture_state(rising(1000+2*i), actual)
    for i in range(2): checks.capture_state(rising(1010+2*i), packet(checks, proposal=i))
    checks.capture_state(rising(1040), packet(checks))
    checks.accepted_burst(tuple((1000+2*i, resolution(t, resolved_path())) for i, t in enumerate(tokens[:2])))
    checks.pending()
    for h, t in enumerate(old): checks.consume('old', h, source(t, 1100+10*h))
    checks.begin_late()
    model.advance(replace(event, feedback=resolution(tokens[2], program.late_path)))
    for _ in range(32):
        if model.sources.tage.offers.get((7, PC%4)): break
        model.advance(event)
    else: raise AssertionError('late independent learning never proposes')
    actual = packet(checks); actual['state']['training']['valid'] = 1
    checks.capture_state(rising(1200), actual)
    checks.late_accepted((1200, resolution(tokens[2], program.late_path)))
    checks.pipeline.last_tick = 1204
    checks.begin_collision(Future(), Future())
    checks.capture_state(rising(1204), packet(checks, proposal=2, ready=True))
    return checks, (model, event, anchor), retired, baseline


def collided(program):
    checks, reference, retired, baseline = held(program)
    actual = packet(checks, proposal=2, ready=True)
    checks.prepare_collision(preparation(1205), actual)
    model, event, _ = reference
    model.advance(replace(event, prediction_ready=False))
    assert model.sources.tage.commits == baseline+2
    checks.capture_state(rising(1206), packet(checks, remaining=True))
    checks.raise_failure()
    for owner in range(2): checks.write_accepted(owner, Transfer(rising(1206), deepcopy(checks.wanted_plan()[owner][0])))
    checks.capture_state(rising(1208), packet(checks, remaining=True))
    checks.pipeline.last_tick = 1208
    checks.collision_complete(checks.receipt.result())
    return checks, reference, retired, baseline


def completed(program):
    checks, reference, retired, baseline = collided(program)
    model, event, anchor = reference
    for h, t in enumerate(consumers(model, event, anchor)): checks.consume('mixed', h, source(t, 1300+10*h))
    checks.pipeline.last_tick = 1400
    checks.release()
    quiet(model, event)
    for owner, values in enumerate(checks.remaining_plan):
        for i, payload in enumerate(values): checks.write_accepted(owner, Transfer(rising(1410+2*i), deepcopy(payload)))
    assert model.sources.tage.commits == baseline+2+sum(program.remaining)
    checks.services_complete()
    final = (revisit(model, event, anchor, PC),)
    middle = revisit(model, event, anchor, VIA_PC)
    final += (streaming_query(model, event, middle.history, PC, VIA_PC+4),)
    checks.capture_state(rising(1500), packet(checks, remaining=True, ready=True, drained=True))
    for h, token in enumerate(final): checks.consume('final', h, source(token, 1600+10*h))
    return checks, retired


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.name)
def test_old_service_new_learning_and_every_real_semantic_consumer(p):
    checks, retired = completed(p)
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish()
    assert checks.closed and len(retired) == 9
    assert checks.coverage.groups['checked'].coverage == 25
    assert checks.collision['tick'] == checks.written[0][0][0] == checks.written[1][0][0]


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.name)
@pytest.mark.parametrize('fault', ('missing-late-branch', 'old-service-counter', 'new-counter-prestate', 'dirty-lost', 'wrong-identity', 'no-actual-service'))
def test_a_candidate_cannot_hide_wrong_old_or_new_ownership(p, fault):
    checks, _, _, _ = held(p)
    actual = packet(checks, proposal=2, ready=True)
    if fault == 'missing-late-branch': actual['state']['incoming'][0]['valid'] = 0
    elif fault == 'old-service-counter': actual['state']['writes'][0]['bits']['counter'] = 0
    elif fault == 'new-counter-prestate': actual['records'][0][0]['counter'] = 0
    elif fault == 'dirty-lost': actual['state']['dirty'] = ((0, 1, 0, 0), (1, 1, 0, 0))
    elif fault == 'wrong-identity': actual['records'][0][0]['tag'] ^= 1
    if fault == 'no-actual-service':
        checks.prepare_collision(preparation(1205), actual)
        with pytest.raises(AssertionError): checks.write_accepted(0, Transfer(rising(1206), deepcopy(checks.wanted_plan()[0][0])))
    else:
        with pytest.raises(AssertionError): checks.prepare_collision(preparation(1205), actual)
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.name)
@pytest.mark.parametrize('fault', ('new-dirty-lost', 'new-counter-lost', 'untouched-neighbor', 'duplicate-old-service'))
def test_correct_old_service_does_not_complete_or_corrupt_new_learning(p, fault):
    checks, _, _, _ = collided(p)
    actual = packet(checks, remaining=True)
    if fault == 'new-dirty-lost': actual['state']['dirty'] = ((0, 0, 0, 0), actual['state']['dirty'][1])
    elif fault == 'new-counter-lost': actual['records'][0][0]['counter'] = 1
    elif fault == 'untouched-neighbor': actual['records'][1][1]['counter'] = 7
    if fault == 'duplicate-old-service':
        with pytest.raises(AssertionError): checks.write_accepted(0, Transfer(rising(1210), checks.wanted_plan()[0][0]))
    else:
        checks.capture_state(rising(1210), actual)
        with pytest.raises(AssertionError) as first: checks.raise_failure()
        with pytest.raises(AssertionError) as second: checks.finish()
        assert first.value is second.value
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('missing', RULES)
def test_checked_credit_waits_for_every_obligation(missing):
    checks, _ = completed(PROGRAMS[0])
    if missing == RULES[-1]: checks.consumers.pop(('final', 1))
    else: checks.coverage.seen.pop(missing)
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.name)
def test_original_snapshot_mutation_is_not_excused_by_correct_final_counts(p):
    checks, _ = completed(p)
    checks.sources[2].meta['original'] ^= 1
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


def test_profile_cannot_be_replaced_by_an_undeclared_physical_variant():
    with pytest.raises(ValueError): Program('bank0', 'both-branches')
    with pytest.raises(ValueError): Program('same-identity', 'way0')
