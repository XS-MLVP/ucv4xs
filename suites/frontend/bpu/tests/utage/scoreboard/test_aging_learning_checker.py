"""Bounded monitor faults cannot receive concurrent-maintenance PASS credit."""
from copy import deepcopy
import ast
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.utage.checker.aging_learning import AgingLearningChecks, payload
from suites.frontend.bpu.utage.model.aging_learning import AgingLearningProgram, POSITION, RULES
from suites.frontend.bpu.utage.model.semantic import Context, TRAIN_HISTORY_INDICES
from suites.frontend.bpu.utage.transaction.types import UtageLookup, UtagePrediction


class CoverageSpy:
    def __init__(self): self.samples = []
    def record(self, status, rule, **witness): self.samples.append((status, rule))


def prediction(expected):
    hit = int(expected.provider is not None)
    slots = tuple(dict(valid=int(slot == 0), cfiPosition=POSITION+slot, baseTaken=expected.base if slot == 0 else 0,
        baseIsStrongBias=0, hit=hit if slot == 0 else 0, tableId=expected.provider or 0,
        takenCtr_value=expected.counter or 0, predTaken=expected.taken if slot == 0 else 0) for slot in range(4))
    return UtagePrediction(hit, expected.taken,
        dict(readIndex=expected.context.index, abtbResult=slots,
             foldedPathHistForTrain_hist=tuple(dict(foldedHist=v)
                 for v in Context.from_recent(expected.context.history).folds)))


def remember(checks, learning, number):
    expected = learning.source
    transfer = SimpleNamespace(sequence_id=number,
        request=UtageLookup(expected.context.pc, POSITION, expected.base, folded_history=expected.context.history),
        accepted_event=SimpleNamespace(tick=10+2*number), completed_event=SimpleNamespace(tick=20+2*number))
    actual = prediction(expected)
    return checks.remember(transfer, actual, expected)


def frame(checks, values, *, public=None, controls=None, sampled=True):
    values = tuple(values)
    row = dict(reset=0, enable=1, public=dict(valid=int(public is not None), bits=public),
        tables=tuple(dict(allocate=0, update=0, age=0) for _ in range(2)) if controls is None else controls)
    if sampled:
        row.update(changes=tuple((i, old, new) for i, (old, new) in enumerate(zip(checks.actual, values)) if old != new),
                   all_cells_sha256=sha256(bytes(values)).hexdigest())
    return SimpleNamespace(value=row, event=SimpleNamespace(tick=1000+2*checks.cycle))


def prepared(program):
    coverage = CoverageSpy()
    checks = AgingLearningChecks(program, coverage)
    checks.observe(frame(checks, program.before))  # Pure checker fixture, not DUT state seeding.
    last = program.failed_source(program.ordinary_failures)
    first = remember(checks, last, 1)
    second = remember(checks, program.target_learning, 2)
    txs = ((first, 'threshold-failure', checks.transaction(first, last)),
           (second, 'overlap-target', checks.transaction(second, program.target_learning)))
    checks.arm()
    checks.plan(txs)
    return checks, coverage, txs


def admitted(checks, txs, *, gap=False):
    for index, (_, _, tx) in enumerate(txs):
        if index and gap:
            checks.observe(frame(checks, checks.program.before))
        checks.observe(frame(checks, checks.program.before, public=payload(tx)))


@pytest.mark.parametrize('table,rule', tuple((t,r) for t in (0,1) for r in RULES))
def test_real_control_pair_common_prestate_complete_poststate_and_all_consumers_are_required(table, rule):
    program = AgingLearningProgram(table, rule)
    checks, coverage, txs = prepared(program)
    admitted(checks, txs)
    checks.observe(frame(checks, program.before, controls=program.controls))
    assert coverage.samples == [('reached', program.name)]
    checks.observe(frame(checks, program.after))
    for read in program.consumers:
        checks.consumer(read, prediction(read))
    checks.finish()
    assert coverage.samples == [('reached', program.name), ('checked', program.name)]


@pytest.mark.parametrize('damage', ('age-only', 'one-table-age', 'wrong-index', 'wrong-reward', 'gap', 'wrong-input', 'missing-input'))
def test_missing_actual_concurrency_or_original_qualification_cannot_claim_reached(damage):
    program = AgingLearningProgram(0, 'reward')
    checks, coverage, txs = prepared(program)
    controls = deepcopy(program.controls)
    with pytest.raises(AssertionError):
        if damage == 'wrong-input':
            actual = payload(txs[0][2]);actual['branch']['taken'] ^= 1
            checks.observe(frame(checks, program.before, public=actual))
        else:
            admitted(checks, txs[:1] if damage == 'missing-input' else txs, gap=damage == 'gap')
        if damage == 'age-only': controls[0]['update'] = 0
        elif damage == 'one-table-age': controls[1]['age'] = 0
        elif damage == 'wrong-index': controls[0]['index'] ^= 1
        elif damage == 'wrong-reward': controls[0]['increase'] = 0
        checks.observe(frame(checks, program.before, controls=controls))
    assert not coverage.samples


def test_learning_without_maintenance_is_not_a_concurrent_event():
    program = AgingLearningProgram(1, 'penalty')
    checks, coverage, txs = prepared(program)
    admitted(checks, txs)
    controls = tuple(dict(row, age=0) for row in program.controls)
    checks.observe(frame(checks, program.after, controls=controls))
    with pytest.raises(AssertionError):checks.finish()
    assert not coverage.samples


@pytest.mark.parametrize('damage', ('double-effect', 'wrong-age-policy', 'foreign-cell', 'missing-snapshot', 'repeat-maintenance'))
def test_wrong_full_protection_effect_keeps_reached_but_never_checked(damage):
    program = AgingLearningProgram(1, 'penalty')
    checks, coverage, txs = prepared(program)
    admitted(checks, txs)
    checks.observe(frame(checks, program.before, controls=program.controls))
    after = list(program.after)
    if damage == 'double-effect': after[512+program.target.index[1]] = 0
    elif damage == 'wrong-age-policy': after[512+program.neighbor.index[1]] = 2
    elif damage == 'foreign-cell': after[0] = 1
    observation = frame(checks, after, sampled=damage != 'missing-snapshot',
                        controls=program.controls if damage == 'repeat-maintenance' else None)
    original = program.after
    checks.capture(observation)
    with pytest.raises(AssertionError) as first:checks.raise_failure()
    with pytest.raises(AssertionError) as repeated:checks.finish()
    assert repeated.value is first.value and program.after == original
    assert coverage.samples == [('reached', program.name)]


@pytest.mark.parametrize('damage', ('counter', 'provider', 'direction', 'history', 'neighbor', 'missing-consumer', 'changed-original'))
def test_wrong_or_missing_fresh_direction_and_source_preservation_cannot_claim_checked(damage):
    program = AgingLearningProgram(0, 'reward')
    checks, coverage, txs = prepared(program)
    admitted(checks, txs)
    checks.observe(frame(checks, program.before, controls=program.controls))
    checks.observe(frame(checks, program.after))
    with pytest.raises(AssertionError):
        for index, read in enumerate(program.consumers):
            actual = prediction(read)
            if index == 0:
                slot = actual.meta['abtbResult'][0]
                if damage == 'counter': slot['takenCtr_value'] += 1
                elif damage == 'provider': slot['tableId'] = 1
                elif damage == 'direction': slot['predTaken'] ^= 1
                elif damage == 'history': actual.meta['foldedPathHistForTrain_hist'][TRAIN_HISTORY_INDICES[0]]['foldedHist'] ^= 1
                elif damage == 'missing-consumer': continue
            if damage == 'neighbor' and read.context == program.neighbor:
                actual.meta['abtbResult'][0]['takenCtr_value'] -= 1
            checks.consumer(read, actual)
        if damage == 'changed-original':
            checks.sources[2]['prediction'].meta['readIndex'] = (0, 0)
        checks.finish()
    assert coverage.samples == [('reached', program.name)]


def test_original_feedback_is_single_use_and_its_payload_is_not_a_mutable_alias():
    program = AgingLearningProgram(0, 'reward')
    checks, _, txs = prepared(program)
    with pytest.raises(AssertionError):checks.transaction(2, program.target_learning)
    txs[1][2].meta['readIndex'] = (0, 0)
    assert checks.sources[2]['prediction'].meta['readIndex'] == program.target.index
    with pytest.raises(AssertionError):checks.transaction(999, program.target_learning)


def test_original_lookup_identity_and_response_age_are_not_fabricated():
    program = AgingLearningProgram(0, 'allocate')
    checks = AgingLearningChecks(program, CoverageSpy())
    source = program.target_learning.source
    handle = SimpleNamespace(sequence_id=1, request=UtageLookup(source.context.pc, POSITION, source.base,
        folded_history=source.context.history), accepted_event=SimpleNamespace(tick=12), completed_event=None)
    with pytest.raises(AssertionError):checks.remember(handle, prediction(source), source)
    handle.completed_event = SimpleNamespace(tick=14)
    handle.request = UtageLookup(source.context.pc+64, POSITION, source.base, folded_history=source.context.history)
    with pytest.raises(AssertionError):checks.remember(handle, prediction(source), source)


@pytest.mark.parametrize('damage', ('wrong-delta-origin', 'duplicate-delta', 'bad-snapshot-hash',
                                  'unplanned-input', 'future-response', 'wrong-logical-source'))
def test_corrupt_observation_or_feedback_lineage_stops_before_reached(damage):
    program = AgingLearningProgram(0, 'reward')
    checks, coverage, txs = prepared(program)
    with pytest.raises(AssertionError):
        if damage == 'wrong-logical-source':
            # A fresh independently published source is not permission to use
            # another context's metadata merely because the position matches.
            extra = remember(checks, program.failed_source(0), 3)
            checks.transaction(extra, program.target_learning)
        else:
            observation = frame(checks, program.before, public=payload(txs[0][2]))
            if damage == 'wrong-delta-origin':
                observation.value['changes'] = ((0, 1, 0),)
            elif damage == 'duplicate-delta':
                observation.value['changes'] = ((0, 0, 0), (0, 0, 0))
            elif damage == 'bad-snapshot-hash':
                observation.value['all_cells_sha256'] = 'wrong'
            elif damage == 'unplanned-input':
                checks.planned.clear()
            elif damage == 'future-response':
                checks.sources[1]['completed'] = observation.event.tick+2
            checks.observe(observation)
    assert not coverage.samples


def test_program_imports_geometry_only_not_the_cycle_reference_or_native_access():
    tree = ast.parse(Path('utage/model/aging_learning.py').read_text())
    imports = [(node.module, tuple(name.name for name in node.names)) for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom)]
    assert imports == [('dataclasses', ('dataclass', 'replace')),
                       ('suites.frontend.bpu.utage.model.semantic', ('Context', 'indices'))]
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
