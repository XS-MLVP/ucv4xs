"""Normal semantic preparation plus adversarial receipts; no DUT coverage."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import pytest

from suites.frontend.bpu.bpu.checker.dual_retirement import DualRetirementChecks
from suites.frontend.bpu.bpu.coverage.dual_retirement import DualRetirementCoverage
from suites.frontend.bpu.bpu.model.tage.dual_retirement import PC, PATHS, OUTCOMES, COMMIT_COUNTERS, counters_after_service
from suites.frontend.bpu.bpu.model.tage.dual_migration import POSITIONS
from tests.bpu.scoreboard.test_dual_migration import fixture as migration_fixture, source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_service import via


def fixture():
    return migration_fixture(checks_type=DualRetirementChecks, coverage_type=DualRetirementCoverage)


def learn(checks, program):
    model, event, _ = program
    idle = quiet(model, event)
    tage, path = model.sources.tage, []
    commits = tage.commits
    context = checks.read(checks.sources[0]).context
    def step(events):
        before = tage.commits
        model.advance(events)
        if tage.commits != before:
            assert tage.commits == before + 2
            read = tage.lookup_snapshot(PC, context)
            path.append(tuple(read.matches(p)[0][2] for p in POSITIONS))
    for s in checks.sources:
        request = resolution(s.token, OUTCOMES)
        assert not model.sources.feedback_for(request).reread
        step(replace(idle, feedback=request))
    for _ in range(16):
        if not model.sources.main_pending(): break
        step(idle)
    else: raise AssertionError('owned paired successors did not retire')
    assert tage.commits == commits + 8
    return tuple(path)


def row(checks, *, proposal=None, training=False):
    ordinal = proposal
    prior = ordinal is not None and ordinal > 0
    return dict(reset=0, reads=({'valid': 0, 'mask': 0}, {'valid': 0, 'mask': 0}),
        training=dict(valid=int(training), ready=1),
        incoming=tuple(dict(valid=int(ordinal is not None), bits=deepcopy(p)) for p in checks.proposal),
        dirty=((int(prior), 0, 0, 0),) * 2,
        writes=tuple(dict(valid=int(prior), ready=1,
            bits=deepcopy(checks.payload(owner, ordinal if prior else 1))) for owner in range(2)))


def observations(checks):
    checks.begin_burst()
    for index in range(4): checks.capture_state(NS(tick=40000 + 2 * index), row(checks, training=True))
    for index in range(4):
        tick = 40008 + 2 * index
        checks.capture_state(NS(tick=tick), row(checks, proposal=index))
        if index >= 2:
            for owner in range(2): checks.write_accepted(owner, NS(accepted_tick=tick, value=deepcopy(checks.payload(owner, index - 1))))
    for ordinal in (3, 4):
        for owner in range(2): checks.write_accepted(owner,
            NS(accepted_tick=40010 + ordinal * 2, value=deepcopy(checks.payload(owner, ordinal))))
    checks.pipeline.last_resolution_controls = 40006, (False, False, True, True, False, False, False)
    return tuple((40000 + 2 * index, resolution(s.token, OUTCOMES)) for index, s in enumerate(checks.sources))


def serviced():
    checks, program, retired = fixture()
    events = observations(checks)
    checks.accepted_burst(events)
    checks.services_complete()
    assert learn(checks, program) == COMMIT_COUNTERS
    return checks, program, retired


def consume(checks, program):
    model, event, anchor = program
    for index, (name, path) in enumerate(PATHS.items()):
        checks.consumed(name, source(model, via(model, event, anchor, path), 40100 + 20 * index))


def test_four_distinct_old_pairs_produce_eight_complete_versions_including_an_unchanged_upper_hold():
    checks, program, _ = fixture()
    assert len(checks.sources) == len({id(s.token.history) for s in checks.sources}) == 4
    assert checks.profile(checks.sources[0]) == ((1, 3), ((7, 0, 2, 0), (7, 1, 5, 0)))
    assert checks.profile(checks.before['original']) == ((0, 1), ((7, 1, 1, 0), (7, 0, 4, 0)))
    old = tuple(deepcopy(s.meta.resolve) for s in checks.sources)
    assert learn(checks, program) == ((0, 5), (0, 6), (0, 7), (0, 7))
    assert tuple(s.meta.resolve for s in checks.sources) == old


def test_all_actual_versions_overlap_and_both_consumers_precede_any_checked_credit():
    checks, program, retired = serviced()
    assert checks.coverage.groups['checked'].coverage == 0 and not retired
    assert len(checks.written[0]) == len(checks.written[1]) == 4
    assert [r['accepts_at'] for r in checks.offered[1:]] == [t for t, _ in checks.written[0][:-1]]
    consume(checks, program)
    assert checks.coverage.groups['checked'].coverage == 0
    checks.finish()
    assert checks.closed and len(retired) == len(set(retired)) == 8
    assert all(g.coverage == 100 for g in checks.coverage.groups.values())


@pytest.mark.parametrize('ordinal,expected', tuple(enumerate(COMMIT_COUNTERS, 1)))
def test_service_ordinal_has_closed_form_logical_counters(ordinal, expected):
    assert counters_after_service(ordinal) == expected


@pytest.mark.parametrize('ordinal', (0, -1, 5, True, 1.0))
def test_no_extra_service_can_be_aliased_to_a_declared_old_pair(ordinal):
    with pytest.raises(ValueError): counters_after_service(ordinal)


@pytest.mark.parametrize('fault', ('reset', 'reread', 'one-input-port', 'old-counter', 'wrong-tag', 'wrong-row',
    'swapped-proposals', 'read-busy', 'missing-ready', 'previous-service-missing', 'previous-old-owner',
    'previous-stale-counter', 'wrong-dirty', 'short-retention', 'proposal-gap', 'proposal-before-input'))
def test_bad_same_cycle_observation_latches_first_error_without_repairing_golden(fault):
    checks, _, _ = fixture(); checks.begin_burst()
    for i in range(4): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    checks.capture_state(NS(tick=40008), row(checks, proposal=0))
    actual, tick = row(checks, proposal=1), 40010
    if fault == 'reset': actual['reset'] = 1
    elif fault == 'reread': actual['reads'][1]['valid'] = 1
    elif fault == 'one-input-port': actual['incoming'][1]['valid'] = 0
    elif fault in ('old-counter', 'wrong-tag', 'wrong-row'):
        actual['incoming'][0]['bits'][{'old-counter': 'counter', 'wrong-tag': 'tag', 'wrong-row': 'row'}[fault]] ^= 1
    elif fault == 'swapped-proposals': actual['incoming'] = tuple(reversed(actual['incoming']))
    elif fault == 'read-busy': actual['reads'][0].update(valid=1, mask=1)
    elif fault == 'missing-ready': actual['writes'][0]['ready'] = 0
    elif fault == 'previous-service-missing': actual['writes'][1]['valid'] = 0
    elif fault == 'previous-old-owner': actual['writes'] = tuple(reversed(actual['writes']))
    elif fault == 'previous-stale-counter': actual['writes'][1]['bits']['counter'] = 1
    elif fault == 'wrong-dirty': actual['dirty'] = ((0, 0, 0, 0),) * 2
    elif fault == 'short-retention': actual['dirty'] = ((1, 0, 0),) * 2
    elif fault == 'proposal-gap': tick += 2
    else: tick = 40002
    state = deepcopy(checks.pipeline.model.sources.tage.state())
    checks.capture_state(NS(tick=tick), actual)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value
    assert checks.pipeline.model.sources.tage.state() == state and checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-pair', 'wrong-origin', 'wrong-target', 'wrong-direction', 'gap',
    'disabled', 'missing-input', 'missing-proposal', 'duplicate-acceptance', 'extra-input', 'extra-proposal'))
def test_each_acceptance_and_proposal_has_exact_original_pair_identity(fault):
    checks, _, _ = fixture(); events = list(observations(checks))
    if fault == 'missing-pair': events.pop()
    elif fault == 'wrong-origin': events[-1] = events[-1][0], events[0][1]
    elif fault in ('wrong-target', 'wrong-direction'):
        r = events[-1][1]; first = r.branches[0]
        first = replace(first, target=first.target + 2) if fault == 'wrong-target' else replace(first, taken=True)
        events[-1] = events[-1][0], replace(r, branches=(first, *r.branches[1:]))
    elif fault == 'gap': events[-1] = events[-1][0] + 2, events[-1][1]
    elif fault == 'disabled': checks.pipeline.last_resolution_controls = 40006, (False,) * 7
    elif fault == 'missing-input': checks.input_ticks.pop()
    elif fault == 'missing-proposal': checks.offered.pop()
    elif fault == 'duplicate-acceptance': checks.accepted_burst(tuple(events))
    elif fault == 'extra-input':
        checks.capture_state(NS(tick=40020), row(checks, training=True))
    else: checks.capture_state(NS(tick=40020), row(checks, proposal=3))
    with pytest.raises(AssertionError): checks.accepted_burst(tuple(events))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('early', 'late', 'old-owner', 'stale-counter', 'lost-update', 'wrong-tag', 'invalid-entry', 'extra'))
def test_actual_sdk_transfer_must_keep_each_full_current_version_not_only_the_final_result(fault):
    checks, _, _ = fixture(); checks.begin_burst()
    for i in range(4): checks.capture_state(NS(tick=40000 + 2 * i), row(checks, training=True))
    checks.capture_state(NS(tick=40008), row(checks, proposal=0))
    owner, tick, payload = 0, 40012, deepcopy(checks.payload(0, 1))
    if fault == 'early': tick -= 2
    elif fault == 'late': tick += 2
    elif fault == 'old-owner': owner = 1
    elif fault == 'stale-counter': payload['counter'] = 6
    elif fault == 'lost-update': payload['counter'] = 4
    elif fault == 'wrong-tag': payload['tag'] ^= 1
    elif fault == 'invalid-entry': payload['valid'] = 0
    else: checks.write_accepted(owner, NS(accepted_tick=tick, value=payload))
    with pytest.raises(AssertionError): checks.write_accepted(owner, NS(accepted_tick=tick, value=payload))
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('owner,index', tuple((o, i) for o in range(2) for i in range(4)))
def test_missing_any_of_eight_sdk_services_prevents_closure(owner, index):
    checks, _, _ = fixture(); checks.accepted_burst(observations(checks))
    del checks.written[owner][index]
    with pytest.raises(AssertionError): checks.services_complete()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('wrong-pair-tick', 'no-sdk-overlap', 'sample-sdk-payload-disagree', 'missing-accept'))
def test_sampled_same_cycle_service_must_agree_with_both_sdk_receipts(fault):
    checks, _, _ = fixture(); checks.accepted_burst(observations(checks))
    if fault == 'wrong-pair-tick': checks.written[1][0] = 40014, checks.written[1][0][1]
    elif fault == 'no-sdk-overlap': checks.offered[1]['accepts_at'] += 2
    elif fault == 'sample-sdk-payload-disagree': checks.offered[1]['retiring'][0]['counter'] = 0
    else: checks.accepted.pop()
    with pytest.raises(AssertionError): checks.services_complete()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('name', tuple(PATHS))
def test_each_fresh_history_consumer_is_mandatory(name):
    checks, program, _ = serviced(); consume(checks, program); del checks.consumers[name]
    with pytest.raises(AssertionError): checks.finish()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('missing-old', 'actual-meta-changed', 'owned-meta-changed', 'repeated-finish'))
def test_original_snapshots_and_single_credit_remain_required(fault):
    checks, program, _ = serviced(); consume(checks, program)
    if fault == 'missing-old': checks.sources.pop()
    elif fault == 'actual-meta-changed': checks.sources[0].meta.resolve['sequence'] ^= 1
    elif fault == 'owned-meta-changed': checks.defined[0]['bad'] = 1
    else: checks.finish()
    with pytest.raises(AssertionError): checks.finish()


def test_case_has_no_private_scheduler_or_raw_signal_operations():
    for path in ('bpu/case/dual_retirement.py', 'tests/bpu/testcase/test_dual_retirement.py'):
        for node in ast.walk(ast.parse(Path(path).read_text())):
            assert not isinstance(node, (ast.Assert, ast.ClassDef))
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', None)
                assert name not in {'ClockCycles', 'RisingEdge', 'FallingEdge', 'set_', 'get_', 'gather', 'create_task', 'Scoreboard'}


def test_post_rise_combinational_snapshot_is_not_an_already_accepted_sdk_transfer():
    checks, _, _ = fixture(); checks.accepted_burst(observations(checks))
    assert checks.offered[0]['tick'] == 40008 and checks.offered[0]['accepts_at'] == 40010
    assert checks.written[0][0][0] == 40012
    assert checks.offered[1]['tick'] == 40010 and checks.offered[1]['accepts_at'] == checks.written[0][0][0]
    checks.services_complete()
