"""Independent source-stage replay, wrong-age association and credit controls."""
from copy import deepcopy
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.mbtb.model.semantic import Events, MbtbReference
from bpuverify.mbtb.transaction.types import MbtbEntry, MbtbPrediction
from bpuverify.common.model.query_reset_program import Program, MODES, RULES
DUTS = ('mbtb',)
from bpuverify.common.model.query_lifetime import QueryLease
from bpuverify.mbtb.coverage.query_reset import Coverage
from bpuverify.mbtb.checker.query_reset import Checks

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
def test_existing_reference_source_stages_derive_the_declared_disposition(dut, mode):
    p, lease = (Program('mbtb', mode), QueryLease())
    pc = p.old[0].pc
    model = MbtbReference()
    for _ in range(2):
        model.advance(Events(pc=pc, select=True, advance=True))
    previous = model.read
    model.advance(Events(pc=pc, select=True, advance=True))
    snapshot = model.read
    assert model.frame is previous and snapshot.pc == previous.pc and (snapshot is not previous)
    lease.accept(snapshot, 10)
    assert not lease.response(model.frame, 10)
    frozen = deepcopy(snapshot)
    if mode == 'response-before-reset':
        model.advance(Events(advance=True))
        assert lease.response(model.frame, 12)
    model.advance(Events(reset=True))
    assert model.frame is model.read is None
    lease.reset(14)
    assert lease.disposition == p.disposition and snapshot == frozen

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('missing', RULES)
def test_partial_query_reset_lifetime_cannot_receive_checked_credit(dut, mode, missing):
    coverage = Coverage(Program('mbtb', mode))
    for rule in RULES:
        if rule != missing:
            coverage.reach(rule)
    with pytest.raises(AssertionError, match='incomplete'):
        coverage.finish()
    assert coverage.groups['checked'].coverage == 0

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('mode', MODES)
def test_complete_lifetime_earns_credit_once_not_for_another_mode(dut, mode):
    coverage = Coverage(Program('mbtb', mode))
    for rule in RULES:
        coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 50
    with pytest.raises(AssertionError):
        coverage.finish()
    with pytest.raises(ValueError):
        coverage.reach(RULES[0])

def prediction(p):
    entries = [MbtbEntry(0, 0, 0, 0, 0, 0) for _ in range(4)]
    for slot, b in zip((0, 2), p.old[:2], strict=True):
        entries[slot] = MbtbEntry(1, 1, b.target, b.position, b.kind, b.action)
    return MbtbPrediction(tuple(entries), [[dict(rawHit=0) for _ in range(2)] for _ in range(2)])

@pytest.mark.parametrize('dut', DUTS)
@pytest.mark.parametrize('fault', ('target', 'position', 'kind', 'action', 'taken', 'missing'))
def test_old_response_comparison_rejects_corrupt_instruction_or_new_epoch_payload(dut, fault):
    p = Program('mbtb', 'response-before-reset')
    actual = prediction(p)
    field = dict(kind='branch_type', action='ras_action', missing='valid').get(fault, fault)
    entries = list(actual.entries)
    entries[0] = replace(entries[0], **{field: getattr(entries[0], field) ^ 1})
    actual = replace(actual, entries=tuple(entries))
    with pytest.raises(ScoreboardMismatch) as error:
        Checks(p).prediction(actual, p.old[0].pc, p.old)
    assert error.value.context.request['program'] == p.state()
