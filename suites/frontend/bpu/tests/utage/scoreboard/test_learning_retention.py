"""Pure lifetime fault controls; these never provide hardware coverage credit."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from toffee import CoverageDatabase, TransferState

from bpuverify.utage.checker.learning_retention import (
    LearningRetentionChecks, RECENT_VERSION_CAPACITY, cohorts)
from bpuverify.utage.coverage.learning_retention import LearningRetentionCoverage, RULES
from bpuverify.utage.model.semantic import Context, indices
from bpuverify.utage.model.usefulness_events import ProtectionState
from bpuverify.utage.model.working_set import PC, POSITION, PHASES, WorkingSetProgram, WorkingSetReference

pytestmark = pytest.mark.toffee_functional_coverage(False)


def counts(coverage, status):
    group, = [group for group in CoverageDatabase(coverage.groups.values()).report()['groups']
              if group['instance'].endswith('.' + status)]
    return group['points'][0]['counts']


def prepared(mode='adjacent', initialize=True):
    program = WorkingSetProgram('turnover', mode)
    reference = WorkingSetReference(program)
    owners = tuple(range(len(program.histories)))
    for owner, history in zip(owners, program.histories, strict=True):
        reference.capture(owner, PHASES[0], history)
    reference.commit(PHASES[0], owners)
    original = NS(meta=dict(owner='initial', counter=4))
    base_checks = NS(reference=reference, originals=[(original, deepcopy(original.meta))])

    # Stub only the existing full prediction checker for protocol unit tests.
    # Native tests use WorkingSetChecks plus the unchanged cycle reference.
    def responses(histories, transfers, predictions, base, states, *, after=None):
        assert len(histories) == len(transfers) == len(predictions)
        for history, transfer, prediction in zip(histories, transfers, predictions, strict=True):
            assert transfer.state is TransferState.COMPLETED
            assert prediction.counter == states[history].counter
            assert transfer.request.folded_history == history
            assert after is None or transfer.accepted_event.tick > after
            base_checks.originals.append((prediction, deepcopy(prediction.meta)))
    base_checks.responses = responses
    base = NS(program=program, checks=base_checks,
        monitor=NS(reference=NS(cycle_ticks=2), cell_comparisons=0),
        agent=NS(reference=NS(raise_failure=lambda: None)))
    coverage = LearningRetentionCoverage(program)
    checks = LearningRetentionChecks(base, coverage)
    if initialize:
        checks.initialize()
    return checks, coverage


def queries(checks, histories, start):
    transfers = tuple(NS(state=TransferState.COMPLETED,
        accepted_event=NS(tick=start + 2 * index), completed_event=NS(tick=start + 2 * index + 4),
        request=NS(pc=PC, position=POSITION, folded_history=history))
        for index, history in enumerate(histories))
    predictions = tuple(NS(counter=checks.states[history].counter,
        meta=dict(history=history, counter=checks.states[history].counter)) for history in histories)
    return transfers, predictions


def learn(checks, *, unrelated=False, fault=None):
    histories = checks.turnover if unrelated else checks.retained
    label = 'unrelated-learning' if unrelated else 'retained-learning'
    transfers, predictions = queries(checks, histories, 400 if unrelated else 100)
    checks.predictions(histories, transfers, predictions)
    payloads = tuple(dict(history=history, pc=PC, counter=4) for history in histories)
    spacing = 2 if checks.base.program.mode == 'adjacent' else 4
    receipts = [(500 if unrelated else 200) + spacing * index for index in range(len(histories))]
    receipts = list(zip(receipts, deepcopy(payloads), strict=True))
    expected = dict(checks.base.checks.reference.states)
    for history in (*checks.retained, *(checks.turnover if unrelated else ())):
        expected[history] = ProtectionState(5, 3)
    values = list(checks.base.checks.reference.values(expected))
    if fault == 'missing-feedback': receipts.pop()
    elif fault == 'wrong-payload': receipts[0][1]['history'] = -1
    elif fault == 'before-source': receipts[0] = (transfers[0].completed_event.tick, receipts[0][1])
    elif fault == 'wrong-cadence': receipts[1] = (receipts[0][0], receipts[1][1])
    elif fault == 'wrong-source-pc': transfers[0].request.pc += 2
    elif fault == 'wrong-source-history': transfers[0].request.folded_history += 1
    elif fault == 'duplicate-original': transfers[1].accepted_event.tick = transfers[0].accepted_event.tick
    elif fault == 'unrelated-state-damage': values[-1] = 1
    checks.accepted_learning(histories, transfers, tuple(receipts), payloads,
                             label=label, actual_values=values)


def consume(checks, *, late=False, fault=None):
    label = 'fresh-after-turnover-consumers' if late else 'immediate-bypass-consumers'
    transfers, predictions = queries(checks, checks.retained, 700 if late else 300)
    if fault == 'stale': transfers[0].accepted_event.tick = 0
    elif fault == 'wrong-counter': predictions[0].counter -= 1
    checks.consumed(checks.retained, transfers, predictions, label=label)


def departure(checks, *, fault=None):
    cells = [dict(valid=1, index=indices(PC, Context.from_recent(history))[1]) for history in checks.turnover]
    observation = NS(event=NS(tick=600), value=dict(cells=cells))
    if fault == 'still-resident': cells[0]['index'] = indices(PC, Context.from_recent(checks.retained[0]))[1]
    elif fault == 'old-observation': observation.event.tick = 0
    elif fault == 'no-observation': observation = None
    checks.confirm_turnover(observation)


def through_departure(checks):
    learn(checks)
    consume(checks)
    learn(checks, unrelated=True)
    departure(checks)


@pytest.mark.parametrize('mode', ('serial', 'adjacent'))
def test_complete_lifetime_only_publishes_its_own_profile_once(mode):
    checks, coverage = prepared(mode)
    through_departure(checks)
    assert not any(counts(coverage, 'checked').values())
    consume(checks, late=True)
    assert not any(counts(coverage, 'checked').values())
    checks.finish()
    wanted = {mode + '.' + rule: 1 for rule in RULES}
    actual = counts(coverage, 'checked')
    assert {key:value for key,value in actual.items() if value} == wanted
    assert coverage.groups['checked'].coverage == 50.0
    with pytest.raises(AssertionError): checks.finish()
    assert counts(coverage, 'checked') == actual


@pytest.mark.parametrize('fault', ('missing-feedback','wrong-payload','before-source','wrong-cadence',
    'wrong-source-pc','wrong-source-history','duplicate-original','unrelated-state-damage'))
def test_learning_requires_actual_owned_inputs_and_preserves_all_other_state(fault):
    checks, coverage = prepared()
    with pytest.raises(AssertionError): learn(checks, fault=fault)
    assert not any(counts(coverage, 'checked').values())


def test_lifetime_cannot_install_another_initial_state_or_learn_before_initialization():
    checks, coverage = prepared(initialize=False)
    histories = checks.retained
    transfers = tuple(NS(accepted_event=NS(tick=index),completed_event=NS(tick=index + 1)) for index in range(8))
    with pytest.raises(AssertionError):
        checks.accepted_learning(histories, transfers, (), (), label='retained-learning', actual_values=())
    assert not any(counts(coverage, 'checked').values())
    checks, coverage = prepared()
    with pytest.raises(AssertionError): checks.initialize()
    assert not any(counts(coverage, 'checked').values())


@pytest.mark.parametrize('fault', ('still-resident','old-observation','no-observation'))
def test_departure_must_be_observed_after_other_identity_learning(fault):
    checks, coverage = prepared()
    learn(checks)
    consume(checks)
    learn(checks, unrelated=True)
    with pytest.raises(AssertionError): departure(checks, fault=fault)
    assert not any(counts(coverage, 'checked').values())


@pytest.mark.parametrize('late', (False, True))
@pytest.mark.parametrize('fault', ('stale','wrong-counter'))
def test_immediate_or_late_response_cannot_borrow_an_old_or_wrong_learning(late, fault):
    checks, coverage = prepared()
    if late: through_departure(checks)
    else: learn(checks)
    with pytest.raises(AssertionError): consume(checks, late=late, fault=fault)
    assert not any(counts(coverage, 'checked').values())


@pytest.mark.parametrize('missing', ('immediate','other-input','departure','late','immutable','default-model'))
def test_finish_never_replaces_missing_evidence_or_repairs_an_earlier_failure(missing):
    checks, coverage = prepared()
    if missing == 'immediate':
        learn(checks)
    elif missing == 'other-input':
        learn(checks); consume(checks)
    elif missing == 'departure':
        learn(checks); consume(checks); learn(checks, unrelated=True)
    else:
        through_departure(checks)
        if missing != 'late': consume(checks, late=True)
    if missing == 'immutable': checks.base.checks.originals[0][0].meta['counter'] = 7
    elif missing == 'default-model':
        def failed(): raise AssertionError('latched independent cycle model mismatch')
        checks.base.agent.reference.raise_failure = failed
    with pytest.raises(AssertionError): checks.finish()
    assert not any(counts(coverage, 'checked').values())


@pytest.mark.parametrize('size', ('turnover','capacity'))
@pytest.mark.parametrize('mode', ('serial','adjacent'))
def test_cohort_selection_retains_both_original_declared_scopes(size, mode):
    program = WorkingSetProgram(size, mode)
    retained, turnover = cohorts(program)
    assert len(retained) == len(turnover) == RECENT_VERSION_CAPACITY
    assert set(retained).isdisjoint(turnover)
    assert set(retained) | set(turnover) <= set(program.histories)
    assert len(program.histories) == (32 if size == 'turnover' else 512)


@pytest.mark.parametrize('status,rule', (('made-up',RULES[0]),('reached','slot3-written')))
def test_unknown_status_or_physical_detail_cannot_be_a_semantic_obligation(status, rule):
    _, coverage = prepared()
    with pytest.raises(ValueError): coverage.record(status, rule)
