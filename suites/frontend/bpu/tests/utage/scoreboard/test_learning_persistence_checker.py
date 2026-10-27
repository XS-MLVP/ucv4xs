"""Exceptions show real point/state; service and storage remain orthogonal."""
import pytest
from toffee import ScoreboardMismatch
from bpuverify.utage.checker.learning_persistence import PersistenceChecks
from bpuverify.utage.model.learning_persistence import Program
from bpuverify.utage.model.persistence import PersistenceLedger, Version


def prepared(*, serviced=True):
    version=Version(10,(1,19,54,6),5,'reward')
    ledger=PersistenceLedger();ledger.source(version,dict(original=10));ledger.accept(dict(original=10),12)
    ledger.publish(*version.identity[:2],version.entry,14)
    if serviced:ledger.service(*version.identity[:2],version.entry,16)
    return PersistenceChecks(Program('retained-window','adjacent'),ledger),version


def test_complete_service_and_storage_are_both_required_for_persistence():
    checks,version=prepared()
    checks.persistent([version.owner],{version.identity[:2]:version.entry},phases=['allocate'])
    assert checks.board.status.checked==checks.board.status.passed==1


@pytest.mark.parametrize('field',('valid','tag','position','counter'))
def test_native_mismatch_shows_the_actual_point_and_owned_state(field):
    checks,version=prepared();actual=version.entry;actual[field]^=1
    with pytest.raises(ScoreboardMismatch) as raised:
        checks.persistent([version.owner],{version.identity[:2]:actual},phases=['allocate'])
    message=str(raised.value)
    assert 'latest accepted learning persists in actual SRAM' in message
    assert 'accepted' in message and 'published' in message and 'services' in message
    assert field in message and checks.board.status.failed==1


def test_matching_storage_without_observed_service_does_not_earn_credit():
    checks,version=prepared(serviced=False)
    with pytest.raises(AssertionError,match='not actually persistent'):
        checks.persistent([version.owner],{version.identity[:2]:version.entry},phases=[])


def test_missing_identity_is_a_comparison_failure_not_a_key_error():
    checks,version=prepared()
    with pytest.raises(ScoreboardMismatch):checks.persistent([version.owner],{},phases=[])


def test_failed_status_remains_json_safe_without_copying_or_replacing_the_error():
    import json
    checks, version = prepared()
    actual = dict(version.entry, counter=4)
    with pytest.raises(ScoreboardMismatch) as raised:
        checks.persistent([version.owner], {version.identity[:2]: actual}, phases=['allocate'])
    snapshot = checks.status_snapshot()
    assert snapshot['failed'] == 1 and snapshot['checked'] == 1
    assert snapshot['first_failure'] == str(raised.value)
    assert 'expected 5, actual 4' in snapshot['first_failure']
    assert checks.board.status.first_failure is raised.value
    assert json.loads(json.dumps(snapshot)) == snapshot
