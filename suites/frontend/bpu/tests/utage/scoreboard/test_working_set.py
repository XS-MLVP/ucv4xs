"""Independent lifetime arithmetic and synthetic checker fault injection.

These tests never receive DUT coverage credit. Real acceptance and consumers
are exercised separately by tests/utage/testcase/test_working_set.py.
"""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from toffee import TransferState

from bpuverify.utage.checker.working_set import WorkingSetChecks
from bpuverify.utage.coverage.working_set import WorkingSetCoverage
from bpuverify.utage.model.semantic import Context, tag
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.utage.model.working_set import (MODES, PHASES, PC, POSITION, SIZES,
    WorkingSetProgram, WorkingSetReference, address, expected)
from bpuverify.utage.transaction.types import UtageLookup, UtagePrediction


def prediction(history, base, state):
    fields = expected(history, base, state)
    slots = tuple(dict(valid=int(i == 0), cfiPosition=POSITION + i,
        baseTaken=base if i == 0 else 0, baseIsStrongBias=0,
        hit=int(i == 0 and state is not None), tableId=1,
        takenCtr_value=0 if state is None else state.counter,
        predTaken=0 if state is None else state.taken) for i in range(4))
    return UtagePrediction(fields['hit'], 0 if state is None else state.taken,
        dict(readIndex=address(history), abtbResult=slots,
             foldedPathHistForTrain_hist=tuple(dict(foldedHist=fold) for fold in fields['folds'])))


def queries(histories, base, states, start):
    transfers = tuple(NS(state=TransferState.COMPLETED, accepted_event=NS(tick=start + 2*i),
        completed_event=NS(tick=start + 2*i + 4),
        request=UtageLookup(PC, POSITION, base, folded_history=history))
        for i, history in enumerate(histories))
    predictions = tuple(prediction(history, base, states.get(history)) for history in histories)
    return histories, transfers, predictions


def phase_inputs(checks, phase):
    start = checks.reference.phase * 100000 + 2
    histories, transfers, predictions = queries(checks.program.order(phase), checks.program.base(phase),
                                                checks.reference.states, start)
    owners = checks.capture(phase, transfers, predictions)
    states = checks.reference.preview(phase, owners)
    payloads = tuple(deepcopy(checks.source_payloads[owner]) for owner in owners)
    step = 2 if checks.program.mode == 'adjacent' else 4
    receipts = tuple((start + 10000 + step*i, payload) for i, payload in enumerate(payloads))
    confirmation = receipts[-1][0] + 10
    consumers = queries(checks.program.histories, 0, states, confirmation + 2)
    return owners, payloads, receipts, confirmation, consumers, list(checks.reference.values(states))


def advance(checks, phase):
    owners, payloads, receipts, confirmation, consumers, values = phase_inputs(checks, phase)
    checks.admissions(phase, owners, receipts, payloads, cycle_ticks=2)
    checks.verified_phase(phase, owners, values, consumers, confirmation_tick=confirmation)


def checks_for(size='turnover', mode='adjacent'):
    program = WorkingSetProgram(size, mode)
    return WorkingSetChecks(program, WorkingSetCoverage(program))


@pytest.mark.parametrize('size', tuple(SIZES))
@pytest.mark.parametrize('mode', MODES)
def test_lifetime_keeps_independent_states_through_turnover_boundary_and_selective_recovery(size, mode):
    checks = checks_for(size, mode)
    for phase, counter, useful in zip(PHASES, (4, 5, 6, 7, 6, 7), (2, 3, 3, 3, 2, 3), strict=True):
        advance(checks, phase)
        selected = set(checks.program.selected)
        for history, state in checks.reference.states.items():
            wanted = ProtectionState(7, 3) if phase == 'selective-penalty' and history not in selected else ProtectionState(counter, useful)
            assert state == wanted
    assert checks.coverage.groups['checked'].coverage == 0
    consumers = queries(checks.program.histories, 0, checks.reference.states, 999999)
    checks.finish(checks.reference.values(), consumers, confirmation_tick=999990)
    assert checks.coverage.groups['checked'].coverage == 25
    assert len(checks.reference.consumed) == 4*SIZES[size] + 2*len(checks.program.selected)
    assert len(checks.program.selected) < 128


@pytest.mark.parametrize('size', tuple(SIZES))
def test_logical_working_set_geometry_and_full_tags_are_explicit_without_missing_row_input(size):
    program = WorkingSetProgram(size, 'serial')
    assert len(program.histories) == len(set(program.histories)) == SIZES[size]
    assert len({address(history)[1] for history in program.histories}) == SIZES[size]
    assert all(tag(PC, Context.from_recent(history), table) < 64
               for history in program.histories for table in (0, 1))
    assert len(program.histories) > 8
    assert len(program.selected) < len(program.histories)


@pytest.mark.parametrize('fault', ('duplicate', 'missing', 'unknown', 'order', 'wrong-phase', 'replay'))
def test_invalid_model_batch_cannot_partially_advance(fault):
    program = WorkingSetProgram('turnover', 'adjacent')
    reference = WorkingSetReference(program)
    phase = PHASES[0]
    for owner, history in enumerate(program.order(phase)):
        reference.capture(owner, phase, history)
    owners = tuple(range(SIZES['turnover']))
    if fault == 'replay':
        reference.commit(phase, owners)
    before = deepcopy(reference.state())
    if fault == 'duplicate': owners = (*owners[:-1], owners[0])
    elif fault == 'missing': owners = owners[:-1]
    elif fault == 'unknown': owners = (*owners[:-1], 9999)
    elif fault == 'order': owners = tuple(reversed(owners))
    elif fault == 'wrong-phase': phase = PHASES[1]
    with pytest.raises(ValueError): reference.commit(phase, owners)
    assert reference.state() == before


@pytest.mark.parametrize('fault', ('target-protection', 'untouched-protection', 'shared-short',
    'missing-consumer', 'stale-consumer', 'wrong-counter', 'wrong-owner', 'early-confirmation',
    'missing-input-qualification'))
def test_bad_learning_or_consumption_cannot_advance_or_gain_checked_credit(fault):
    checks = checks_for()
    for phase in PHASES[:4]: advance(checks, phase)
    phase = 'selective-penalty'
    owners, payloads, receipts, confirmation, consumers, values = phase_inputs(checks, phase)
    if fault != 'missing-input-qualification':
        checks.admissions(phase, owners, receipts, payloads, cycle_ticks=2)
    selected = checks.program.selected[0]
    untouched = next(h for h in checks.program.histories if h not in checks.program.selected)
    if fault == 'target-protection': values[512 + address(selected)[1]] ^= 1
    elif fault == 'untouched-protection': values[512 + address(untouched)[1]] ^= 1
    elif fault == 'shared-short': values[address(selected)[0]] ^= 1
    elif fault == 'missing-consumer': consumers = tuple(part[:-1] for part in consumers)
    elif fault == 'stale-consumer': consumers[1][0].accepted_event.tick = confirmation
    elif fault == 'wrong-counter': consumers[2][0].meta['abtbResult'][0]['takenCtr_value'] ^= 1
    elif fault == 'wrong-owner': consumers[1][0].request = replace(consumers[1][0].request, folded_history=untouched)
    elif fault == 'early-confirmation': confirmation = receipts[-1][0]
    before = deepcopy(checks.reference.state())
    with pytest.raises(AssertionError):
        checks.verified_phase(phase, owners, values, consumers, confirmation_tick=confirmation)
    assert checks.reference.state() == before
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing', 'reorder', 'changed-payload', 'invented-source', 'bubble', 'before-source'))
def test_feedback_requires_original_full_payloads_and_actual_acceptance(fault):
    checks = checks_for()
    owners, payloads, receipts, _, _, _ = phase_inputs(checks, PHASES[0])
    if fault == 'missing': receipts = receipts[:-1]
    elif fault == 'reorder': receipts = tuple((tick, payloads[-1-i]) for i, (tick, _) in enumerate(receipts))
    elif fault == 'changed-payload': receipts[0][1]['meta']['readIndex'] = (123, 456)
    elif fault == 'invented-source':
        # Mutating both expected plan and actual payload must not fool the checker.
        payloads[0]['meta']['abtbResult'][0]['takenCtr_value'] ^= 1
    elif fault == 'bubble': receipts = tuple((tick + 2*int(i > 0), payload) for i, (tick, payload) in enumerate(receipts))
    else: receipts = tuple((2*i, payload) for i, (_, payload) in enumerate(receipts))
    with pytest.raises(AssertionError):
        checks.admissions(PHASES[0], owners, receipts, payloads, cycle_ticks=2)
    assert checks.coverage.groups['reached'].coverage == 2.5  # source overlap only
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-output', 'unfinished', 'no-overlap', 'wrong-history', 'wrong-folds'))
def test_sources_require_complete_owned_overlapping_actual_queries(fault):
    checks = checks_for()
    _, transfers, predictions = queries(checks.program.order(PHASES[0]), 0, {}, 2)
    if fault == 'missing-output': predictions = predictions[:-1]
    elif fault == 'unfinished': transfers[0].state = TransferState.PROCESSING
    elif fault == 'no-overlap': transfers[1].accepted_event.tick = transfers[0].completed_event.tick
    elif fault == 'wrong-history': transfers[1].request = replace(transfers[1].request, folded_history=999)
    else: predictions[0].meta['foldedPathHistForTrain_hist'][0]['foldedHist'] ^= 1
    with pytest.raises(AssertionError): checks.capture(PHASES[0], transfers, predictions)
    assert not checks.reference.sources
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('mutated-snapshot', 'missing-obligation', 'missing-late-consumer'))
def test_end_of_test_cannot_hide_incomplete_or_mutated_originals(fault):
    checks = checks_for()
    for phase in PHASES: advance(checks, phase)
    consumers = queries(checks.program.histories, 0, checks.reference.states, 999999)
    if fault == 'mutated-snapshot': checks.originals[0][0].meta['abtbResult'][0]['baseTaken'] ^= 1
    elif fault == 'missing-obligation': checks.completed.remove(PHASES[2])
    else: consumers = tuple(part[:-1] for part in consumers)
    with pytest.raises(AssertionError):
        checks.finish(checks.reference.values(), consumers, confirmation_tick=999990)
    assert checks.coverage.groups['checked'].coverage == 0


def test_case_has_no_timing_io_or_async_join_and_model_has_no_observation_dependencies():
    case = ast.parse(Path('bpuverify/utage/case/working_set.py').read_text())
    forbidden = {'ClockCycles', 'RisingEdge', 'FallingEdge', 'gather', 'create_task', 'get_', 'set_'}
    assert not {node.id for node in ast.walk(case) if isinstance(node, ast.Name)} & forbidden
    assert not {node.attr for node in ast.walk(case) if isinstance(node, ast.Attribute)} & forbidden
    model = ast.parse(Path('bpuverify/utage/model/working_set.py').read_text())
    assert not any(isinstance(node, ast.ImportFrom) and node.module and any(
        part in node.module.split('.') for part in ('monitor', 'driver', 'bundle', 'toffee'))
        for node in ast.walk(model))


@pytest.mark.parametrize('capacity', (2, 4, 64))
async def test_environment_streams_beyond_framework_capacity_without_enlarging_queue_or_whole_batch_timeout(capacity):
    from bpuverify.utage.env.working_set import WorkingSetEnv

    class Transfer:
        def __init__(self, agent, history): self.agent, self.history = agent, history
        def __await__(self):
            async def complete():
                self.agent.outstanding -= 1
                return self.history
            return complete().__await__()

    class Agent:
        def __init__(self):
            self.prediction_scoreboard = NS(capacity=capacity)
            self.outstanding = self.peak = self.drains = 0
        def submit_predict(self, pc, position, base, *, folded_history):
            assert self.outstanding < capacity
            self.outstanding += 1
            self.peak = max(self.peak, self.outstanding)
            return Transfer(self, folded_history)
        async def drain_predictions(self):
            assert self.outstanding == 0
            self.drains += 1

    agent = Agent()
    program = WorkingSetProgram('capacity', 'adjacent')
    env = WorkingSetEnv(agent, program, WorkingSetCoverage(program), None)
    histories, transfers, predictions = await env.read(program.histories, 0)
    assert histories == predictions == program.histories
    assert len(transfers) == 512 and agent.peak == capacity and agent.drains == 1
