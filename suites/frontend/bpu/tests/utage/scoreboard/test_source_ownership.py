"""Independent discriminators and counterfactual failures; no DUT is driven."""
from copy import deepcopy
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import ast
import json

import pytest
from toffee import ScoreboardMismatch, TransferState
from suites.frontend.bpu.utage.checker.source_ownership import SourceOwnershipChecks
from suites.frontend.bpu.utage.model.semantic import Context, Events, tag
from suites.frontend.bpu.utage.model.source_ownership import AssociationProgram, ASSOCIATION_MODES, Profile, RecoveryProgram
from suites.frontend.bpu.utage.monitor.source_ownership import SourceObservation, SourceOwnershipMonitor
from suites.frontend.bpu.utage.transaction.types import UtagePrediction


class CoverageSpy:
    def __init__(self): self.samples = []
    def record(self, status, rule, **witness): self.samples.append((status, rule))


def prediction(profile, *, base=1, history=None):
    fields = profile.expected(base, override_history=history)
    slots = tuple(dict(valid=int(i == 0), hit=int(fields['hit'] if i == 0 else 0),
        tableId=0, takenCtr_value=profile.counter or 0, predTaken=int((profile.counter or 0) >= 4),
        baseTaken=base if i == 0 else 0, baseIsStrongBias=0, cfiPosition=5+i) for i in range(4))
    return UtagePrediction(fields['hit'], int((profile.counter or 0) >= 4),
        dict(readIndex=profile.indices, foldedPathHistForTrain_hist=tuple(dict(foldedHist=f) for f in fields['folds']),
             abtbResult=slots), (fields['hit'], 0, 0, 0), (int((profile.counter or 0) >= 4), 0, 0, 0))


def recovery_rows(program):
    p = program
    events = tuple(Events(read_pc=source.pc, read_context=source.context, select=True, advance=True)
                   for source in p.profiles)
    events += (Events(read_pc=p.decoy.pc, read_context=p.decoy.context, select=True, advance=True,
        override=p.stage, override_pc=p.target.pc, override_context=Context.from_recent(p.history)),)
    outputs = (prediction(p.decoy), prediction(p.old), prediction(p.young), prediction(p.target, history=p.history))
    cell = dict(valid=1, data_valid=1, index=p.target.indices[0], tag=tag(p.target.pc, p.target.context, 0),
                position=5, counter=p.latest.counter)
    return tuple(SourceObservation(10+2*i, event, output, dict(enq=1, cells=(deepcopy(cell),)*8))
                 for i, (event, output) in enumerate(zip(events, outputs, strict=True)))


@pytest.mark.parametrize('mode', ASSOCIATION_MODES)
def test_declared_profiles_distinguish_input_identity_and_prediction_before_drive(mode):
    p = AssociationProgram(mode)
    assert tuple(s.counter for s in p.profiles) == (5, 2, 4, None)
    assert len({s.indices for s in p.profiles}) == 4
    assert len(p.sequence) == 8 and {s.name for s, _ in p.sequence} == {'old','young','decoy','cold'}
    assert all(tag(s.pc, s.context, 0) < 256 for s in p.profiles[:3])
    if mode == 'history-only': assert len({s.pc for s in p.profiles}) == 1
    if mode == 'pc-only': assert len({s.history for s in p.profiles}) == 1


@pytest.mark.parametrize('stage', ('s2','s3'))
@pytest.mark.parametrize('learning', (False,True))
@pytest.mark.parametrize('retag', (False,True))
def test_hand_derived_saved_age_direction_and_latest_version_are_distinct(stage, learning, retag):
    p = RecoveryProgram(stage, learning=learning, retag=retag)
    assert p.target.counter == (2 if stage == 's2' else 5)
    assert p.latest.counter == ((1 if stage == 's2' else 6) if learning else p.target.counter)
    fields = p.target.expected(1, override_history=p.history)
    assert fields['hit'] == int(not retag) and fields['indices'] == p.target.indices
    assert ('counter' in fields) == (not retag)
    checks = SourceOwnershipChecks(p, CoverageSpy())
    rows = recovery_rows(p);checks.lineage(rows, (1,2,3,4));checks.recovery(rows[-1])


@pytest.mark.parametrize('stage', ('s2','s3'))
@pytest.mark.parametrize('damage', ('other-age','latest-instead-of-saved','normal-read-decoy','wrong-source-index'))
def test_wrong_age_latest_or_decoy_fails_with_semantic_program_state(stage, damage):
    p = RecoveryProgram(stage, learning=True); row = recovery_rows(p)[-1]
    other = p.old if stage == 's2' else p.young
    if damage == 'other-age': actual = prediction(other)
    elif damage == 'latest-instead-of-saved': actual = prediction(p.latest)
    elif damage == 'normal-read-decoy': actual = prediction(p.decoy)
    else:
        actual = prediction(p.target);actual.meta['readIndex'] = other.indices
    coverage = CoverageSpy();checks = SourceOwnershipChecks(p, coverage)
    with pytest.raises(ScoreboardMismatch) as error:checks.recovery(replace(row, prediction=actual))
    assert ('checked','selected-snapshot') not in coverage.samples
    assert error.value.context.request['program']['stage'] == stage
    assert error.value.expected != error.value.actual


@pytest.mark.parametrize('stage', ('s2','s3'))
def test_post_recovery_learning_cannot_pretend_latest_was_already_visible(stage):
    p = RecoveryProgram(stage, learning=True); row = recovery_rows(p)[-1]
    row.shadow['cells'][0]['counter'] = p.target.counter
    coverage = CoverageSpy();checks = SourceOwnershipChecks(p, coverage)
    with pytest.raises(ScoreboardMismatch):checks.recovery(row)
    assert ('checked','new-content-visible') not in coverage.samples


@pytest.mark.parametrize('stage', ('s2','s3'))
@pytest.mark.parametrize('damage', ('swapped-inputs','no-advance','wrong-recovery-history','wrong-recovery-pc'))
def test_bad_actual_lineage_cannot_qualify_the_same_recovery(stage, damage):
    p = RecoveryProgram(stage); rows = list(recovery_rows(p))
    if damage == 'swapped-inputs': rows[0],rows[1] = rows[1],rows[0]
    elif damage == 'no-advance':rows[2] = replace(rows[2], inputs=replace(rows[2].inputs, advance=False))
    elif damage == 'wrong-recovery-history':rows[3] = replace(rows[3], inputs=replace(rows[3].inputs, override_context=Context()))
    else:rows[3] = replace(rows[3], inputs=replace(rows[3].inputs, override_pc=p.decoy.pc))
    coverage = CoverageSpy()
    with pytest.raises(ScoreboardMismatch):SourceOwnershipChecks(p, coverage).lineage(rows, (1,2,3,4))
    assert ('checked','actual-input-lineage') not in coverage.samples


@pytest.mark.parametrize('stage', ('s2','s3'))
def test_retag_miss_does_not_invent_a_defined_direction_payload(stage):
    p = RecoveryProgram(stage, retag=True);actual = prediction(p.target, history=p.history)
    actual.meta['abtbResult'][0]['takenCtr_value'] = 7
    actual.meta['abtbResult'][0]['predTaken'] ^= 1
    actual = replace(actual, taken=1-actual.taken)
    SourceOwnershipChecks(p, CoverageSpy()).recovery(replace(recovery_rows(p)[-1], prediction=actual))


@pytest.mark.parametrize('damage', ('serialized','missing-response','not-completed'))
def test_false_overlap_or_missing_completion_cannot_claim_pipeline_credit(damage):
    p = AssociationProgram('mixed'); items = [SimpleNamespace(state=TransferState.COMPLETED,
        accepted_event=SimpleNamespace(tick=2*i), completed_event=SimpleNamespace(tick=2*i+4)) for i in range(8)]
    if damage == 'serialized':items[1].accepted_event.tick = 10
    elif damage == 'missing-response':items.pop()
    else:items[0].state = TransferState.PROCESSING
    coverage = CoverageSpy()
    with pytest.raises(ScoreboardMismatch):SourceOwnershipChecks(p, coverage).overlapping(items)
    assert ('checked','actual-overlap') not in coverage.samples


def test_all_adopted_utage_contracts_preserve_recipes_and_do_not_claim_old_pass_as_new_proof():
    plan = json.loads(Path('verification_plan.json').read_text());features = plan['features']
    utage = [p for p in features if p['id'].startswith('BPU-UTAGE-')]
    # BPU-UTAGE-028 adds the whole-array useful-aging sweep as a genuinely
    # new semantic point discovered by the RTL coverage gap, so the adopted
    # set grows by exactly one while every older contract is preserved.
    assert len(utage) == 28 and all('contract' in p for p in utage)
    assert {p['id'] for p in utage} == {f'BPU-UTAGE-{n:03d}' for n in range(1, 29)}
    assert sum('contract' in p for p in features) >= 47
    adopted = [p for p in utage if p['metadata'].get('semantic_review',{}).get('adopted_event_review')]
    assert len(adopted) == 18
    for point in adopted:
        assert point['metadata']['semantic_review']['scenario_detail']
        assert point['metadata']['semantic_review']['evidence_limits']
        assert '后端提交执行真值' in point['contract']['scope']


def test_logical_source_program_does_not_import_native_signals_drivers_or_checkers():
    tree = ast.parse(Path('utage/model/source_ownership.py').read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imports == {'dataclasses','suites.frontend.bpu.utage.model.semantic'}


@pytest.mark.parametrize('damage', ('counter','history','index','base','position','valid'))
def test_complete_request_response_identity_cannot_be_replaced_by_latest_wire_data(damage):
    program = AssociationProgram('mixed'); profile = program.profiles[0]
    actual = prediction(profile)
    if damage == 'counter': actual.meta['abtbResult'][0]['takenCtr_value'] = 2
    elif damage == 'history': actual.meta['foldedPathHistForTrain_hist'][2]['foldedHist'] ^= 1
    elif damage == 'index': actual.meta['readIndex'] = program.profiles[1].indices
    elif damage == 'base': actual.meta['abtbResult'][0]['baseTaken'] ^= 1
    elif damage == 'position': actual.meta['abtbResult'][0]['cfiPosition'] += 1
    else: actual.meta['abtbResult'][1]['valid'] = 1
    with pytest.raises(ScoreboardMismatch):SourceOwnershipChecks(program, CoverageSpy()).profile(profile, actual, 1)


@pytest.mark.parametrize('damage', ('missing','duplicate','too-early'))
def test_recovery_monitor_requires_one_actual_override_and_three_source_records(damage):
    program = RecoveryProgram('s2'); rows = recovery_rows(program)
    if damage == 'missing': rows = rows[:3]
    elif damage == 'duplicate': rows = (*rows, rows[-1])
    else: rows = rows[2:]
    with pytest.raises(AssertionError):
        SourceOwnershipMonitor.recovery_rows(SimpleNamespace(records=rows), program)


def test_changed_original_snapshot_never_gets_immutable_credit():
    program = AssociationProgram('mixed');actual = prediction(program.profiles[0]);frozen = deepcopy(actual.meta)
    actual.meta['readIndex'] = program.profiles[1].indices
    coverage = CoverageSpy()
    with pytest.raises(ScoreboardMismatch):SourceOwnershipChecks(program, coverage).immutable(((actual, frozen),))
    assert ('checked','immutable-sources') not in coverage.samples


def test_delayed_monitor_delivery_uses_captured_input_identity_not_latest_input():
    monitor = object.__new__(SourceOwnershipMonitor)
    monitor.agent = SimpleNamespace(reference_monitor=SimpleNamespace(last_inputs='newer input'))
    monitor.records = deque()
    old = Events(read_pc=123, select=True)
    monitor.observe(SimpleNamespace(event=SimpleNamespace(tick=10), value=(old, 'actual response', {})))
    assert monitor.records[0].inputs is old
    assert monitor.records[0].prediction == 'actual response'
