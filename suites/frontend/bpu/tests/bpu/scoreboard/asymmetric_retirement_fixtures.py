"""Synthetic observations for checker qualification, never DUT coverage evidence."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

from suites.frontend.bpu.bpu.checker.asymmetric_retirement import AsymmetricRetirementChecks
from suites.frontend.bpu.bpu.coverage.asymmetric_retirement import AsymmetricRetirementCoverage
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.model.tage.asymmetric_retirement import OUTCOMES, PRE_DIRTY_COUNTS
from suites.frontend.bpu.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC, learning_inflight
from tests.bpu.scoreboard.test_neighbor_migration import fixture
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def armed():
    checks, (model, event, anchor), retired = fixture(checks_type=AsymmetricRetirementChecks,
                                                   coverage_type=AsymmetricRetirementCoverage)
    before = source(model, via(model, event, anchor, HISTORY_PATHS['original']), 35000)
    request = resolution(before.token, OUTCOMES[1])
    model.advance(replace(quiet(model, event), feedback=request))
    current = {name: source(model, via(model, event, anchor, path), 36000 + 20 * i)
               for i, (name, path) in enumerate(HISTORY_PATHS.items())}
    checks.arm_asymmetric(before, (35020, request), current)
    return checks, (model, event, anchor), retired


def packet(checks, *, index=None, training=False):
    proposals = (None, None) if index is None else checks.expected_offers[index]
    dirty = (2, 2) if index is None else PRE_DIRTY_COUNTS[index]
    hits, ranks = [], []
    for port, p in enumerate(proposals):
        owner = (1 if index == 0 or index >= 3 and port == 0 else 0) if p is not None and (index == 0 or index >= 3) else None
        hits.append(dict(owner0=(int(owner == 0), 0, 0), owner1=int(owner == 1)))
        ranks.append((int(index is not None and index >= 3 and port == 1), 0))
    return dict(state=dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        training=dict(valid=int(training), ready=1), prediction=dict(valid=1, ready=1, pc=STREAM_PC),
        incoming=tuple(dict(valid=int(p is not None), bits={} if p is None else deepcopy(p)) for p in proposals),
        dirty=tuple((1,) * n + (0,) * (4 - n) for n in dirty),
        writes=tuple(dict(valid=1, ready=0, bits={}) for _ in range(2))),
        owner_hits=tuple(hits), hit_ranks=tuple(ranks))


def submit(checks, program, first, last):
    model, event, _ = program
    base = 40000 if first == 0 else 40100
    events = []
    for i in range(first, last):
        request = resolution(checks.requests[i].token, OUTCOMES[i])
        tick = base + 2 * (i - first)
        checks.capture_state(NS(tick=tick), packet(checks, training=True))
        model.advance(replace(event, feedback=request))
        events.append((tick, request))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):
            break
    else:
        raise AssertionError('independent asymmetric learning did not mature')
    for i in range(first, last):
        checks.capture_state(NS(tick=base + 8 + 2 * (i - first)), packet(checks, index=i))
    checks.pipeline.last_resolution_controls = events[-1][0], event.enabled
    checks.accepted_burst(tuple(events))
    checks.pending()


def held(*, prelude_only=False):
    checks, program, retired = armed()
    model, event, anchor = program
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    checks.begin_read_window()
    submit(checks, program, 0, 3)
    if not prelude_only:
        submit(checks, program, 3, 5)
    return checks, program, retired


def consumers(checks, program, phase):
    model, event, anchor = program
    if phase == 'serviced':
        quiet(model, event)
    for i, (name, path) in enumerate(HISTORY_PATHS.items()):
        if phase == 'blocked':
            mid = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
            token = streaming_query(model, event, mid.history, PC, path + 4)
        else:
            token = via(model, event, anchor, path)
        checks.consume(phase, name, source(model, token, (40200 if phase == 'blocked' else 40400) + 20 * i))


def released():
    checks, program, retired = held()
    consumers(checks, program, 'blocked')
    checks.pipeline.last_tick = 40300
    checks.release()
    return checks, program, retired


def completed():
    checks, program, retired = released()
    for index in range(2):
        for owner in range(2):
            checks.write_accepted(owner, NS(accepted_tick=40310 + 2 * index,
                                           value=deepcopy(checks.expected_plan[owner][index])))
    checks.services_complete()
    consumers(checks, program, 'serviced')
    return checks, program, retired
