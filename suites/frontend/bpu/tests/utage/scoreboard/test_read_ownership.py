"""Pure ownership witnesses and negative controls; never DUT coverage credit."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import ast
import json

import pytest
from toffee import ScoreboardMismatch, TransferState

from suites.frontend.bpu.utage.checker.read_ownership import ReadOwnershipChecks
from suites.frontend.bpu.utage.env.read_ownership import ReadOwnershipEnv
from suites.frontend.bpu.utage.model.read_ownership import FeedbackLedger, ReadOwnershipProgram, RETAINED_VERSIONS, RULES
from suites.frontend.bpu.utage.model.semantic import Context, Entry, Events, UtageReference, tag
from suites.frontend.bpu.utage.monitor.source_ownership import SourceObservation
from suites.frontend.bpu.utage.transaction.types import UtageLookup
from tests.utage.scoreboard.test_semantic_model import BASES, POSITIONS, feedback, learn, lookup
from tests.utage.scoreboard.test_source_ownership import CoverageSpy, prediction


def prepared_model():
    program = ReadOwnershipProgram()
    model = UtageReference()
    for ordinal, result in enumerate(program.preparation):
        base = int(ordinal == 0)
        bases = (replace(BASES[0], taken=bool(base)), *BASES[1:])
        source = lookup(model, result.pc, result.history, bases=bases)
        learn(model, feedback(source, taken=bool(result.taken)))
        observed = lookup(model, result.pc, result.history, bases=bases)
        assert observed.frame.providers()[0] == 0
        assert observed.frame.read.entries[0].counter == result.counter
    return program, model


def window_rows():
    p = ReadOwnershipProgram()
    before_cell = dict(valid=1, data_valid=1, index=p.original.indices[0],
        tag=tag(p.original.pc, p.original.context, 0), position=5, counter=3)
    after_cell = dict(valid=1, data_valid=1, index=p.learning.indices[0],
        tag=tag(p.learning.pc, p.learning.context, 0), position=5, counter=7)
    inputs = Events(read_pc=p.original.pc, read_context=p.original.context, select=True,
                    pc=p.learning.pc, context=p.learning.context, advance=True)
    actual = prediction(p.original, base=0, history=p.learning.history)
    rows = tuple(SourceObservation(tick, inputs, deepcopy(actual), dict(
        public=dict(valid=0), cells=(cell,)*8, hits=(1, 0, 0, 0, 0, 0, 0, 0),
        response=dict(hit=1, valid=1, tag=cell['tag'], position=5, counter=cell['counter'])))
        for tick, cell in ((10, before_cell), (12, after_cell)))
    # Only one physical position is reused; the others are retained B records.
    rows = (replace(rows[0], shadow={**rows[0].shadow,
        'cells': (before_cell, *(deepcopy(after_cell) for _ in range(7)))}), rows[1])
    request = UtageLookup(p.learning.pc, 5, 0, folded_history=p.learning.history,
                          index_pc=p.original.pc, index_history=p.original.history)
    transfers = tuple(SimpleNamespace(request=request, state=TransferState.COMPLETED,
        accepted_event=SimpleNamespace(tick=tick), completed_event=SimpleNamespace(tick=tick+4))
        for tick in (8, 10, 12, 14))
    return p, rows, transfers


def test_normal_feedback_versions_establish_discriminating_records_without_state_seeding():
    p, model = prepared_model()
    assert len(p.preparation) == RETAINED_VERSIONS == 8
    assert [s.counter for s in p.preparation] == [3, 4, 5, 6, 7, 7, 7, 7]
    assert p.original.indices[0] == 11 and p.learning.indices[0] == 27
    assert tag(p.original.pc, p.original.context, 0) == 29
    assert tag(p.learning.pc, p.learning.context, 0) == 15
    assert model.updates[0].sequence == RETAINED_VERSIONS
    assert model.updates[0].newest(p.original.indices[0]).entry.counter == 3


def test_inflight_original_read_remains_a_logical_snapshot_after_other_learning_reuses_retention():
    p, model = prepared_model()
    source = lookup(model, p.learning.pc, p.learning.history)
    query = Events(read_pc=p.original.pc, read_context=p.original.context, select=True,
        pc=p.learning.pc, context=p.learning.context, positions=POSITIONS, bases=BASES, advance=True)
    model.advance(replace(query, feedback=feedback(source)))
    original = model.read
    assert original.entries[0] == Entry(True, 29, 5, 3)
    model.advance(query)
    model.advance(query)
    assert model.updates[0].sequence == RETAINED_VERSIONS + 1
    assert model.updates[0].newest(p.original.indices[0]) is None
    assert model.updates[0].newest(p.learning.indices[0]).entry == Entry(True, 15, 5, 7)
    assert model.prediction.frame.read.entries[0] == original.entries[0]
    assert model.prediction.frame.providers()[0] is None
    assert model.prediction.values()['0.hit'] == 0
    for profile in (p.original, p.learning):
        fresh = lookup(model, profile.pc, profile.history)
        assert fresh.frame.providers()[0] == 0
        assert fresh.frame.read.entries[0].counter == profile.counter
    assert lookup(model, p.neighbor.pc, p.neighbor.history).frame.providers()[0] is None


@pytest.mark.parametrize('damage', ('duplicate-capture', 'duplicate-consume', 'unknown-source'))
def test_feedback_requires_a_fresh_original_query_once(damage):
    ledger = FeedbackLedger(); p = ReadOwnershipProgram()
    ledger.capture('accepted-query-1', p.original, dict(counter=3))
    ledger.consume('accepted-query-1')
    with pytest.raises(ValueError):
        if damage == 'duplicate-capture': ledger.capture('accepted-query-1', p.original, {})
        elif damage == 'duplicate-consume': ledger.consume('accepted-query-1')
        else: ledger.consume('not-accepted')


def test_feedback_ledger_freezes_source_values_independently_of_later_mutation():
    ledger = FeedbackLedger(); metadata = dict(rows=[dict(counter=3)])
    ledger.capture(1, ReadOwnershipProgram().original, metadata)
    metadata['rows'][0]['counter'] = 7
    assert ledger.consume(1)[1] == dict(rows=[dict(counter=3)])


def test_actual_reuse_requires_original_read_and_actual_accepted_query_at_the_boundary():
    p, rows, transfers = window_rows(); coverage = CoverageSpy()
    checks = ReadOwnershipChecks(p, coverage)
    witness = checks.actual_reuse(rows, transfers)
    assert witness['reuse_tick'] == 12 and witness['physical_slot'] == 0
    assert witness['query_accepted_ticks'] == (8, 10)
    assert ('reached', 'actual-inflight-reuse') in coverage.samples
    assert not any(status == 'checked' for status, _ in coverage.samples)


@pytest.mark.parametrize('damage', ('no-reuse', 'other-read', 'not-selected', 'no-advance',
                                   'other-matching-ancestor', 'serialized', 'already-completed',
                                   'wrong-query', 'wrong-query-pc', 'wrong-return-index', 'wrong-return-history'))
def test_final_b_content_or_serialized_queries_cannot_claim_inflight_reuse(damage):
    p, rows, transfers = window_rows(); rows = list(rows)
    if damage == 'no-reuse': rows[1].shadow['cells'] = rows[0].shadow['cells']
    elif damage == 'other-read': rows[0] = replace(rows[0], inputs=replace(rows[0].inputs, read_context=Context()))
    elif damage == 'not-selected': rows[0] = replace(rows[0], inputs=replace(rows[0].inputs, select=False))
    elif damage == 'no-advance': rows[0] = replace(rows[0], inputs=replace(rows[0].inputs, advance=False))
    elif damage == 'other-matching-ancestor': rows[0] = replace(rows[0], inputs=replace(rows[0].inputs, context=Context()))
    elif damage == 'serialized':
        for item in transfers: item.accepted_event.tick += 10
    elif damage == 'already-completed':
        for item in transfers: item.completed_event.tick = 9
    elif damage == 'wrong-query':
        for item in transfers: item.request = replace(item.request, index_history=p.learning.history)
    elif damage == 'wrong-query-pc':
        for item in transfers: item.request = replace(item.request, pc=p.learning.pc+1)
    elif damage == 'wrong-return-index': rows[1].prediction.meta['readIndex'] = p.learning.indices
    else: rows[1].prediction.meta['foldedPathHistForTrain_hist'] = tuple(dict(foldedHist=0) for _ in p.learning.context.folds)
    coverage = CoverageSpy()
    with pytest.raises(ScoreboardMismatch): ReadOwnershipChecks(p, coverage).actual_reuse(rows, transfers)
    assert ('reached', 'actual-inflight-reuse') not in coverage.samples


@pytest.mark.parametrize('damage', ('other-record', 'history', 'index', 'base', 'position', 'valid', 'missing', 'pending'))
def test_wrong_or_incomplete_query_response_cannot_receive_checked_credit(damage):
    p, rows, transfers = window_rows(); actuals = [deepcopy(rows[-1].prediction) for _ in transfers]
    if damage == 'other-record':
        actuals[0] = prediction(p.learning, base=0)
        actuals[0].meta['readIndex'] = p.original.indices
    elif damage == 'history': actuals[0].meta['foldedPathHistForTrain_hist'][0]['foldedHist'] ^= 1
    elif damage == 'index': actuals[0].meta['readIndex'] = p.learning.indices
    elif damage == 'base': actuals[0].meta['abtbResult'][0]['baseTaken'] = 1
    elif damage == 'position': actuals[0].meta['abtbResult'][0]['cfiPosition'] += 1
    elif damage == 'valid': actuals[0].meta['abtbResult'][1]['valid'] = 1
    elif damage == 'missing': actuals.pop()
    else: transfers[0].state = TransferState.PROCESSING
    coverage = CoverageSpy(); checks = ReadOwnershipChecks(p, coverage)
    with pytest.raises(ScoreboardMismatch): checks.responses(transfers, actuals)
    assert not any(status == 'checked' for status, _ in coverage.samples)


def test_miss_has_no_defined_counter_or_raw_direction_but_keeps_its_identity():
    p, rows, transfers = window_rows(); actual = deepcopy(rows[-1].prediction)
    actual.meta['abtbResult'][0]['takenCtr_value'] = 7
    actual.meta['abtbResult'][0]['predTaken'] = 1
    ReadOwnershipChecks(p, CoverageSpy()).responses(transfers, (actual,)*len(transfers))


@pytest.mark.parametrize('damage', ('missing-feedback', 'changed-feedback', 'unconsumed-source'))
def test_feedback_receipts_compare_original_payload_and_exact_count(damage):
    p = ReadOwnershipProgram(); ledger = FeedbackLedger()
    expected = tuple(dict(source=i) for i in range(RETAINED_VERSIONS+1))
    for i, row in enumerate(expected): ledger.capture(i, p.learning, row); ledger.consume(i)
    checks = ReadOwnershipChecks(p, CoverageSpy()); checks.public_feedback = deepcopy(list(expected))
    if damage == 'missing-feedback': checks.public_feedback.pop()
    elif damage == 'changed-feedback': checks.public_feedback[0]['source'] = 99
    else: ledger.capture('unused', p.learning, {})
    with pytest.raises(ScoreboardMismatch): checks.feedback_once(ledger, expected)


def test_no_partial_obligation_can_publish_checked_and_mutated_sources_fail():
    p = ReadOwnershipProgram(); coverage = CoverageSpy(); checks = ReadOwnershipChecks(p, coverage)
    with pytest.raises(ScoreboardMismatch): checks.finish(())
    assert not any(status == 'checked' for status, _ in coverage.samples)
    actual = prediction(p.original); frozen = deepcopy(actual.meta)
    actual.meta['readIndex'] = p.learning.indices
    with pytest.raises(ScoreboardMismatch): checks.finish(((actual, frozen),)*9)


def test_complete_checked_group_requires_all_obligations_and_immutable_sources():
    p = ReadOwnershipProgram(); coverage = CoverageSpy(); checks = ReadOwnershipChecks(p, coverage)
    checks.completed.update(set(RULES)-{'immutable-original-sources'})
    actual = prediction(p.original)
    checks.finish(((actual, deepcopy(actual.meta)),)*9)
    assert {rule for status, rule in coverage.samples if status == 'checked'} == set(RULES)


def test_semantic_program_has_no_native_driver_checker_or_actual_state_imports():
    tree = ast.parse(Path('utage/model/read_ownership.py').read_text())
    assert {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} == {
        'copy', 'dataclasses', 'suites.frontend.bpu.utage.model.semantic', 'suites.frontend.bpu.utage.model.source_ownership'}
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))


def test_adopted_definition_has_existing_feature_identity_and_paired_dut_evidence():
    plan = json.loads(Path('verification_plan.json').read_text())
    # This contract owns UTAGE-006, not the number of requirements in other DUTs.
    matches = [p for p in plan['features'] if p['id'] == 'BPU-UTAGE-006']
    assert len(matches) == 1
    point, = matches
    assert 'inflight_learning_ownership' in point['metadata']
    assert 'tests/utage/testcase/test_read_ownership.py' in point['evidence']['checks']
    assert 'kunminghu_v3.utage.inflight-learning-ownership.checked' in point['evidence']['coverage']['checked']


def test_case_does_not_drive_edges_or_gather_and_source_identity_is_real_transfer_identity():
    case = Path('utage/case/read_ownership.py').read_text()
    env = Path('utage/env/read_ownership.py').read_text()
    assert not any(name in case+env for name in ('ClockCycles', 'RisingEdge', 'FallingEdge', 'asyncio.gather', '.Set('))
    assert 'transfer.sequence_id' in env and 'self.source_tokens[id(source)]' in env
    assert len(ReadOwnershipEnv.LEARNING_INTERVALS) == 4
