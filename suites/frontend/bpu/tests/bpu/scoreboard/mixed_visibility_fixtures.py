"""Synthetic observations qualify the checker, never actual DUT coverage."""
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

from toffee import XEvent, XEventKind, XPhase

from bpuverify.bpu.checker.mixed_visibility import MixedVisibilityChecks
from bpuverify.bpu.coverage.mixed_visibility import MixedVisibilityCoverage
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES, PRELUDE_PLAN
from bpuverify.bpu.model.tage.mixed_visibility import PARTIAL_PLAN, DESTINATIONS, FIRST_SERVICE
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS
from bpuverify.bpu.model.tage.service import STREAM_PC
from tests.bpu.scoreboard.asymmetric_retirement_fixtures import packet as initial_packet
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_neighbor_migration import fixture
from tests.bpu.scoreboard.test_partial_reuse import transfer
from tests.bpu.scoreboard.test_mixed_visibility_model import mature


def armed(program):
    checks, (model, event, anchor), retired = fixture(
        checks_type=lambda p, c: MixedVisibilityChecks(p, c, program),
        coverage_type=lambda: MixedVisibilityCoverage(program))
    before = source(model, via(model, event, anchor, HISTORY_PATHS['original']), 35000)
    request = resolution(before.token, OUTCOMES[1])
    model.advance(replace(quiet(model, event), feedback=request))
    current = {name: source(model, via(model, event, anchor, path), 36000 + 20 * i)
               for i, (name, path) in enumerate(HISTORY_PATHS.items())}
    checks.arm_asymmetric(before, (35020, request), current)
    if 'old-neighbor' in program.late_sources:
        checks.save_old_neighbor(source(model, via(model, event, anchor, HISTORY_PATHS['neighbor']), 37000))
    return checks, (model, event, anchor), retired


def packet(checks, *, training=False, index=None, plan=None):
    proposals = (None, None) if index is None else checks.expected_offers[index]
    if plan is None:
        plan = checks.program.final_plan if checks.refill_qualified else PARTIAL_PLAN
    hits, ranks = [], []
    for logical in ((None, None) if index is None else checks.program.late_proposals[index - 3]):
        owner, rank = (None, None) if logical is None else DESTINATIONS[logical[0]]
        hits.append(dict(owner0=(int(owner == 0), 0, 0), owner1=int(owner == 1)))
        ranks.append(tuple(rank if owner == i else 0 for i in range(2)))
    return dict(state=dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        training=dict(valid=int(training), ready=1), prediction=dict(valid=1, ready=1, pc=STREAM_PC),
        incoming=tuple(dict(valid=int(p is not None), bits={} if p is None else deepcopy(p)) for p in proposals),
        dirty=checks.dirty_for(plan), writes=tuple(dict(valid=1, ready=0, bits={}) for _ in range(2))),
        owner_hits=tuple(hits), hit_ranks=tuple(ranks))


def consumers(checks, reference, phase):
    model, event, anchor = reference
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        if phase == 'serviced':
            token = via(model, event, anchor, path)
        else:
            mid = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
            token = streaming_query(model, event, mid.history, PC, path + 4)
        base = dict(initial=40040, mixed=40200, blocked=40400, serviced=40600)[phase]
        checks.consume(phase, name, source(model, token, base + 20 * i))


def held(program):
    checks, reference, retired = armed(program)
    model, event, anchor = reference
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    checks.begin_read_window()
    receipts = []
    for i, (s, outcomes) in enumerate(zip(checks.requests[:3], OUTCOMES[:3], strict=True)):
        request = resolution(s.token, outcomes)
        checks.capture_state(NS(tick=40000 + 2 * i), initial_packet(checks, training=True))
        model.advance(replace(event, feedback=request))
        receipts.append((40000 + 2 * i, request))
    mature(model, event)
    for i in range(3):
        checks.capture_state(NS(tick=40008 + 2 * i), initial_packet(checks, index=i))
    checks.pipeline.last_resolution_controls = 40004, event.enabled
    checks.accepted_burst(tuple(receipts)); checks.pending()
    consumers(checks, reference, 'initial')
    return checks, reference, retired


def prepared(checks):
    row = packet(checks, plan=PRELUDE_PLAN)
    row['state']['reads'][0]['valid'] = 0
    for owner, p in enumerate(row['state']['writes']):
        p.update(ready=1, bits=checks.payload(FIRST_SERVICE[owner]))
    event = XEvent(event_id=40099, tick=40099, phase=XPhase.DRIVE_STABLE, kind=XEventKind.DRIVE_STABLE)
    checks.prepare_partial(event, row)


def mixed(program):
    checks, reference, retired = held(program)
    model, event, _ = reference
    checks.pipeline.last_tick = 40090
    checks.begin_partial(Future(), Future())
    prepared(checks)
    before = model.sources.tage.commits
    model.advance(replace(event, prediction_ready=False))
    assert model.sources.tage.commits == before + 2
    for owner in range(2):
        checks.write_accepted(owner, transfer(40100, checks.payload(FIRST_SERVICE[owner])))
    for _ in range(8):
        model.advance(event)
    checks.capture_state(NS(tick=40102), packet(checks, plan=PARTIAL_PLAN))
    checks.pipeline.last_tick = 40102
    checks.partial_complete(checks.partial_receipt.result())
    consumers(checks, reference, 'mixed')
    return checks, reference, retired


def relearned(program):
    checks, reference, retired = mixed(program)
    model, event, _ = reference
    checks.arm_mixed()
    receipts = []
    for i, (s, outcomes) in enumerate(zip(checks.requests[3:], program.late_outcomes, strict=True)):
        request = resolution(s.token, outcomes)
        tick = 40300 + 2 * i
        checks.capture_state(NS(tick=tick), packet(checks, training=True))
        model.advance(replace(event, feedback=request))
        receipts.append((tick, request))
    mature(model, event)
    for i in range(len(program.late_sources)):
        checks.capture_state(NS(tick=40308 + 2 * i), packet(checks, index=3 + i, plan=program.pending_before(i)))
    checks.pipeline.last_resolution_controls = receipts[-1][0], event.enabled
    checks.accepted_burst(tuple(receipts)); checks.pending()
    consumers(checks, reference, 'blocked')
    return checks, reference, retired


def released(program):
    checks, reference, retired = relearned(program)
    checks.pipeline.last_tick = 40500
    checks.release()
    return checks, reference, retired


def completed(program):
    checks, reference, retired = released(program)
    for owner, versions in enumerate(checks.expected_plan):
        for index, payload in enumerate(versions):
            checks.write_accepted(owner, transfer(40510 + 2 * index, payload))
    checks.services_complete()
    quiet(reference[0], reference[1])
    consumers(checks, reference, 'serviced')
    return checks, reference, retired
