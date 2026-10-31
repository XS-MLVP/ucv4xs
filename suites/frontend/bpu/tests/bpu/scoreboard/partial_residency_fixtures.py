"""SYNTHETIC checker observations; never exported as actual DUT evidence."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

from toffee import Scoreboard

from suites.frontend.bpu.bpu.checker.partial_residency import PartialResidencyChecks
from suites.frontend.bpu.bpu.coverage.partial_residency import PartialResidencyCoverage
from suites.frontend.bpu.bpu.model.pipeline import Redirect
from suites.frontend.bpu.bpu.model.tage.partial_residency import PC, PATHS
from suites.frontend.bpu.bpu.model.tage.service import STREAM_PC, learning_inflight
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import streaming_query, via
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_partial_residency import prepare_program


def receipt(model, token, tick):
    return NS(token=token, prediction_tick=tick, meta_tick=tick + 4,
              meta=NS(resolve=dict(sequence=token.sequence, fields=deepcopy(model.sources.defined_metadata(token)))))


def armed(program):
    model, event, anchor, sources, current = prepare_program(program)
    retired = []
    pipeline = NS(model=model, board=Scoreboard('partial-residency-contract'),
        source_token=lambda s: s.token, raise_failure=lambda: None, retire_source=retired.append,
        last_tick=40000, last_resolution_controls=(40000, event.enabled))
    checks = PartialResidencyChecks(pipeline, PartialResidencyCoverage(program), program)
    checks.prepared_labels = [s.name for s in checks.intents]
    for index, (name, token) in enumerate(sources.items()):
        checks.save_source(name, receipt(model, token, 100 + index * 20))
    checks.arm({name: receipt(model, token, 30000 + index * 20)
                for index, (name, token) in enumerate(current.items())})
    return checks, (model, event, anchor), retired


def packet(checks, *, training=False, index=None):
    proposals = (None, None) if index is None else checks.expected_offers[index]
    dirty = (None, None) if index in (None, 0) else checks.stage.pending_after[index - 1]
    resident = index is not None and (checks.program.name == 'resident-only'
        or checks.program.name == 'evicted-pending-replace' and index == 0)
    return dict(state=dict(reset=0, reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        prediction=dict(valid=1, ready=1, pc=STREAM_PC), training=dict(valid=int(training), ready=1),
        incoming=tuple(dict(valid=int(p is not None), bits={} if p is None else deepcopy(p)) for p in proposals),
        dirty=tuple((int(p is not None), 0, 0, 0) for p in dirty),
        writes=tuple(dict(valid=0, ready=0, bits={}) for _ in range(2))),
        owner_hits=(dict(owner0=(0, 0, 0), owner1=int(resident)), dict(owner0=(0, 0, 0), owner1=0)))


def held(checks, program):
    model, event, anchor = program
    ordinal = checks.stage_index + 1
    checks.begin_stage(ordinal)
    checks.begin_read_window()
    base = 40000 + ordinal * 1000
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    requests = []
    for index, (name, outcomes) in enumerate(zip(checks.stage.sources, checks.stage.outcomes, strict=True)):
        request = resolution(checks.saved[name].token, outcomes)
        requests.append((base + 2 * index, request))
        checks.capture_state(NS(tick=base + 2 * index), packet(checks, training=True))
        model.advance(replace(event, feedback=request))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):
            break
    for index in range(len(requests)):
        checks.capture_state(NS(tick=base + 8 + 2 * index), packet(checks, index=index))
    checks.pipeline.last_resolution_controls = requests[-1][0], event.enabled
    checks.accepted_burst(tuple(requests))
    checks.pending()
    return checks


def consumers(checks, program, phase):
    model, event, anchor = program
    base = 40100 + checks.stage_index * 1000 + (100 if phase == 'serviced' else 0)
    if phase == 'serviced':
        quiet(model, event)
    for index, (name, path) in enumerate(PATHS.items()):
        if phase == 'blocked':
            mid = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
            token = streaming_query(model, event, mid.history, PC, path + 4)
        else:
            token = via(model, event, anchor, path)
        checks.consume(phase, name, receipt(model, token, base + 20 * index))


def drain(checks, program):
    consumers(checks, program, 'blocked')
    base = 40150 + checks.stage_index * 1000
    checks.pipeline.last_tick = base
    checks.release()
    for owner, payloads in enumerate(checks.expected_plan):
        for payload in payloads:
            checks.write_accepted(owner, NS(accepted_tick=base + 10, value=deepcopy(payload)))
    checks.services_complete()
    consumers(checks, program, 'serviced')
    return checks


def completed(program):
    checks, reference, retired = armed(program)
    for _ in program.stages:
        held(checks, reference)
        drain(checks, reference)
    return checks, reference, retired
