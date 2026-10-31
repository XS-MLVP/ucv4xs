"""Pure fault controls have no hardware functional-coverage credit."""
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace as NS

import pytest
from toffee import CoverageDatabase, TransferState

from suites.frontend.bpu.checkers.pipeline_ownership import check_batch_completed, check_owned_stream
from suites.frontend.bpu.coverage.pipeline_ownership import (
    PipelineOwnershipCoverage, PROFILES, RULES, ownership_coverage)

pytestmark = pytest.mark.toffee_functional_coverage(False)


@dataclass(frozen=True)
class Request:
    pc: int
    history: int


def batch():
    originals = tuple(Request(0x1000 + index * 0x20, index * 4) for index in range(4))
    transfers = tuple(NS(sequence_id=index, request=deepcopy(request),
        accepted_event=NS(tick=10 + index * 2), completed_event=NS(tick=16 + index * 2),
        state=TransferState.COMPLETED, expected=lambda actual: None) for index, request in enumerate(originals))
    return transfers, originals


@pytest.mark.parametrize('fault', ('request-swap', 'history-swap', 'duplicate-id', 'not-completed',
    'explicit-expected', 'missing-acceptance', 'missing-completion', 'backwards-time',
    'same-acceptance', 'same-completion', 'serialized-not-overlapped', 'missing-transfer'))
def test_original_occurrence_audit_rejects_faults(fault):
    transfers, originals = batch()
    if fault == 'request-swap': transfers[1].request = originals[2]
    elif fault == 'history-swap': transfers[1].request = Request(originals[1].pc, originals[2].history)
    elif fault == 'duplicate-id': transfers[1].sequence_id = transfers[0].sequence_id
    elif fault == 'not-completed': transfers[1].state = TransferState.PROCESSING
    elif fault == 'explicit-expected': transfers[1].expected = 7
    elif fault == 'missing-acceptance': transfers[1].accepted_event = None
    elif fault == 'missing-completion': transfers[1].completed_event = None
    elif fault == 'backwards-time': transfers[1].completed_event.tick = transfers[1].accepted_event.tick
    elif fault == 'same-acceptance': transfers[1].accepted_event.tick = transfers[0].accepted_event.tick
    elif fault == 'same-completion': transfers[1].completed_event.tick = transfers[0].completed_event.tick
    elif fault == 'serialized-not-overlapped': transfers[1].accepted_event.tick = transfers[0].completed_event.tick + 1
    elif fault == 'missing-transfer': transfers = transfers[:-1]
    with pytest.raises(AssertionError):
        check_owned_stream(transfers, originals, strict_overlap=True)


def test_receipts_preserve_distinct_occurrences_without_mutable_request_aliases():
    transfers, originals = batch()
    receipts = check_owned_stream(transfers, originals, strict_overlap=True)
    assert [row['request'] for row in receipts] == list(originals)
    assert len({row['source_id'] for row in receipts}) == len(originals)
    assert [row['accepted_tick'] for row in receipts] == [10, 12, 14, 16]


def test_single_cycle_overlap_includes_the_prior_completion_boundary():
    transfers, originals = batch()
    for transfer in transfers:
        transfer.completed_event.tick = transfer.accepted_event.tick + 2
    check_owned_stream(transfers, originals, strict_overlap=False)
    with pytest.raises(AssertionError):
        check_owned_stream(transfers, originals, strict_overlap=True)


def test_empty_or_single_request_is_not_overlapping_stream_evidence():
    transfers, originals = batch()
    for count in (0, 1):
        with pytest.raises(AssertionError):
            check_owned_stream(transfers[:count], originals[:count], strict_overlap=True)


FIELDS = ('submitted', 'accepted', 'checked', 'completed')
IDLE = ('failed', 'pending', 'processing', 'unmatched_requests', 'unmatched_observations')


@pytest.mark.parametrize('fault', (*FIELDS, *IDLE, 'none'))
def test_completion_requires_exact_scoreboard_accounting_and_no_residue(fault):
    before = NS(**dict.fromkeys(FIELDS, 20))
    after = NS(**dict.fromkeys(FIELDS, 24), **dict.fromkeys(IDLE, 0))
    if fault in FIELDS: setattr(after, fault, 23)
    if fault in IDLE: setattr(after, fault, 1)
    if fault == 'none':
        check_batch_completed(before, after, 4)
    else:
        with pytest.raises(AssertionError): check_batch_completed(before, after, 4)


@pytest.mark.parametrize('dut', PROFILES)
def test_distinct_semantic_profiles_keep_complete_paired_denominators(dut):
    coverage = PipelineOwnershipCoverage(dut, PROFILES[dut][0])
    for rule in RULES: coverage.record('reached', rule)
    report = CoverageDatabase(coverage.groups.values()).report()
    groups = {row['instance'].split('.')[-1]:row for row in report['groups']}
    assert groups['checked']['coverage'] == 0
    assert len(groups['reached']['points'][0]['counts']) == len(PROFILES[dut]) * len(RULES)
    for rule in RULES: coverage.record('checked', rule)
    assert coverage.groups['checked'].coverage == 100 / len(PROFILES[dut])
    assert coverage.groups['checked'].definition.digest == ownership_coverage(dut, 'checked').definition.digest


@pytest.mark.parametrize('dut,profile', (('bpu','forward'), ('ubtb','bank0'), ('ittage','forward')))
def test_physical_or_undeclared_profiles_cannot_obtain_semantic_credit(dut, profile):
    with pytest.raises(ValueError): PipelineOwnershipCoverage(dut, profile)
