"""Hand-derived semantic outcomes and false-credit controls, never a DUT drive."""
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.checker.usefulness_events import UsefulnessChecks
from suites.frontend.bpu.utage.model.semantic import Context, indices, tag
from suites.frontend.bpu.utage.model.usefulness_events import (
    HISTORY, NEIGHBOR_HISTORY, PC, SHORT_CONSUMER_HISTORY,
    MODES, ProtectionState, UsefulnessProgram,
)
from suites.frontend.bpu.utage.transaction.types import UtageTraining


OUTCOMES = (
    ('reward', (1, 3), (6, 3)), ('penalty', (5, 0), (2, 0)),
    ('upper-hold', (0, 3), (7, 3)), ('lower-hold', (6, 0), (0, 0)),
    ('reverse-from-upper', (3, 1), (3, 1)), ('reverse-from-lower', (6, 2), (0, 2)),
    ('base-agreement-interior', (1, 1), (6, 2)),
    ('base-agreement-upper', (0, 3), (7, 3)), ('base-agreement-lower', (6, 0), (0, 0)),
)


class CoverageSpy:
    def __init__(self): self.samples = []
    def record(self, status, **witness): self.samples.append(status)


def response(program, state):
    return SimpleNamespace(hit=1, taken=state.taken, meta={'abtbResult': [
        dict(tableId=program.table, takenCtr_value=state.counter)]})


@pytest.mark.parametrize('table', (0, 1))
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('rule,short,long', OUTCOMES)
def test_hand_derived_protection_and_direction_do_not_depend_on_observed_state(table, mode, rule, short, long):
    p = UsefulnessProgram(table, rule, mode)
    assert p.expected[-1] == ProtectionState(*(short if table == 0 else long))
    assert len(p.expected) == 2
    assert p.initial.useful == table + 1
    if rule.startswith('reverse-from'):
        assert p.prepared.useful in (0, 3) and p.expected[-1].useful not in (0, 3)
    if rule == 'lower-hold':
        assert p.source.taken != p.prepared.taken


def test_declared_history_consumers_and_learned_neighbor_have_distinct_ownership():
    contexts = tuple(Context.from_recent(h) for h in (HISTORY, SHORT_CONSUMER_HISTORY, NEIGHBOR_HISTORY))
    a, b, neighbor = (indices(PC, c) for c in contexts)
    assert a[0] == b[0] != neighbor[0] and a[1] != b[1] != neighbor[1] != a[1]
    assert tag(PC, contexts[0], 0) == tag(PC, contexts[1], 0)
    assert tag(PC, contexts[0], 1) != tag(PC, contexts[1], 1)


@pytest.mark.parametrize('damage', ('stale-counter', 'wrong-direction', 'wrong-provider', 'neighbor'))
def test_wrong_complete_target_or_neighbor_never_gets_checked_credit(damage):
    p = UsefulnessProgram(0, 'reward');coverage = CoverageSpy();checks = UsefulnessChecks(p, coverage)
    checks.admissions(((10, 'source'), (20, 'source')), ('source', 'source'), cycle_ticks=2)
    target, neighbor = response(p, p.expected[-1]), response(p, p.initial)
    if damage == 'stale-counter': target.meta['abtbResult'][0]['takenCtr_value'] = 3
    elif damage == 'wrong-direction': target.taken = 1-target.taken
    elif damage == 'wrong-provider': target.meta['abtbResult'][0]['tableId'] = 1
    else: neighbor.meta['abtbResult'][0]['takenCtr_value'] = 6
    with pytest.raises(ScoreboardMismatch) as error:
        checks.consumers(target, neighbor)
        checks.finish((), ())
    assert coverage.samples == ['reached']
    assert error.value.context.request['state']['program']['rule'] == 'reward'
    assert error.value.expected != error.value.actual


@pytest.mark.parametrize('damage', ('bubble', 'wrong-payload', 'partial-offer'))
def test_failed_event_qualification_cannot_claim_reached(damage):
    p = UsefulnessProgram(0, 'reward', 'adjacent');coverage = CoverageSpy();checks = UsefulnessChecks(p, coverage)
    actual = ((10, 'source'), (12, 'source'))
    if damage == 'bubble': actual = ((10, 'source'), (14, 'source'))
    elif damage == 'wrong-payload': actual = ((10, 'other'), (12, 'source'))
    else: actual = actual[:1]
    with pytest.raises(ScoreboardMismatch):checks.admissions(actual, ('source', 'source'), cycle_ticks=2)
    assert not coverage.samples


@pytest.mark.parametrize('damage', ('no-inputs', 'no-consumer', 'changed-original'))
def test_missing_endpoint_or_mutated_original_cannot_claim_checked(damage):
    p = UsefulnessProgram(0, 'reward');coverage = CoverageSpy();checks = UsefulnessChecks(p, coverage)
    if damage != 'no-inputs':checks.admissions(((10, 'source'), (20, 'source')), ('source', 'source'), cycle_ticks=2)
    if damage == 'changed-original':checks.consumers(response(p, p.expected[-1]), response(p, p.initial))
    with pytest.raises(ScoreboardMismatch):checks.finish(('original',), ('changed',) if damage == 'changed-original' else ('original',))
    assert 'checked' not in coverage.samples


def test_actual_public_receipt_accessor_does_not_return_expected_payload_or_mutable_alias():
    checker = UtageUsefulChecker(mode='serial')
    checker._accepted[10] = dict(payload={'expected': 1}, actual_payload={'actual': [2]})
    received = checker.accepted_feedback
    assert received == ((10, {'actual': [2]}),)
    received[0][1]['actual'].append(3)
    assert checker.accepted_feedback == ((10, {'actual': [2]}),)


def test_receipt_is_copied_from_actually_matched_observation_not_a_later_mutable_payload():
    slot = dict(valid=1, cfiPosition=5, hit=0, tableId=0, baseTaken=1, predTaken=0)
    meta = dict(readIndex=[43, 110], abtbResult=[slot])
    tx = UtageTraining(PC, 5, 0, meta)
    checker = UtageUsefulChecker(mode='serial')
    checker.plan((tx,), phase='model-only public capture')
    public = checker._payload(tx)
    row = dict(reset=0, enable=1, public=dict(valid=1, bits=public),
               tables=[dict(allocate=0, update=0, age=0) for _ in range(2)],
               changes=(), all_cells_sha256=sha256(bytes(1024)).hexdigest())
    checker.observe(SimpleNamespace(value=row, event=SimpleNamespace(tick=10)))
    frozen = deepcopy(public)
    public['meta']['readIndex'][0] = 1
    tx.meta['readIndex'][1] = 1
    assert checker.accepted_feedback == ((10, frozen),)


@pytest.mark.parametrize('counter,useful', ((-1, 0), (8, 0), (0, -1), (0, 4), (True, 0), (0, True)))
def test_invalid_logical_state_is_rejected(counter, useful):
    with pytest.raises(ValueError):ProtectionState(counter, useful)


@pytest.mark.parametrize('args', ((2, 'reward', 'serial'), (True, 'reward', 'serial'),
    (0, 'bank-enumeration', 'serial'), (0, 'reward', 'unknown'), (0, 'initial-protection', 'adjacent')))
def test_unknown_scope_and_single_input_adjacent_credit_are_rejected(args):
    with pytest.raises(ValueError):UsefulnessProgram(*args)
