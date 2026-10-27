"""Independent source-stage replay, wrong-age association and credit controls."""
from copy import deepcopy
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.ubtb.model.semantic import UbtbEvents, UbtbReference
from bpuverify.ubtb.transaction.types import PredictRequest, UbtbPrediction
from bpuverify.mbtb.transaction.types import MbtbEntry, MbtbPrediction
from bpuverify.common.model.query_reset_program import Program, MODES, RULES
DUTS = ('ubtb',)
from bpuverify.common.model.query_lifetime import QueryLease
from bpuverify.ubtb.coverage.query_reset import Coverage
from bpuverify.ubtb.checker.query_reset import Checks

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
def test_existing_reference_source_stages_derive_the_declared_disposition(dut, mode):
    p, lease = (Program('ubtb', mode), QueryLease())
    pc = p.old[0].pc
    model = UbtbReference()
    model.advance(UbtbEvents(predict=PredictRequest(pc)))
    previous = model.lookup
    model.advance(UbtbEvents(predict=PredictRequest(pc)))
    snapshot = model.lookup
    assert snapshot.pc == previous.pc and snapshot is not previous
    lease.accept(snapshot, 10)
    frozen = deepcopy(snapshot)
    assert lease.response(model.lookup, 10)
    model.advance(UbtbEvents(reset=True))
    assert model.lookup is None
    lease.reset(14)
    assert lease.disposition == p.disposition and snapshot == frozen

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('missing', RULES)
def test_partial_query_reset_lifetime_cannot_receive_checked_credit(dut, mode, missing):
    coverage = Coverage(Program('ubtb', mode))
    for rule in RULES:
        if rule != missing:
            coverage.reach(rule)
    with pytest.raises(AssertionError, match='incomplete'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
def test_complete_lifetime_earns_credit_once_not_for_another_mode(dut, mode):
    coverage = Coverage(Program('ubtb', mode))
    for rule in RULES:
        coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 50
    with pytest.raises(AssertionError):
        coverage.finish()
    with pytest.raises(ValueError):
        coverage.reach(RULES[0])

def prediction(p):
    b = p.old[0]
    return UbtbPrediction(1, 1, b.target, b.position, b.kind, b.action)
    entries = [MbtbEntry(0, 0, 0, 0, 0, 0) for _ in range(4)]
    for slot, b in zip((0, 2), p.old[:2], strict=True):
        entries[slot] = MbtbEntry(1, 1, b.target, b.position, b.kind, b.action)
    return MbtbPrediction(tuple(entries), [[dict(rawHit=0) for _ in range(2)] for _ in range(2)])

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('fault', ('target', 'position', 'kind', 'action', 'taken', 'missing'))
def test_old_response_comparison_rejects_corrupt_instruction_or_new_epoch_payload(dut, fault):
    p = Program('ubtb', 'response-before-reset')
    actual = prediction(p)
    field = dict(kind='branch_type', action='ras_action', missing='valid').get(fault, fault)
    actual = replace(actual, **{field: getattr(actual, field) ^ 1})
    with pytest.raises(ScoreboardMismatch) as error:
        Checks(p).prediction(actual, p.old[0].pc, p.old)
    assert error.value.context.request['program'] == p.state()
