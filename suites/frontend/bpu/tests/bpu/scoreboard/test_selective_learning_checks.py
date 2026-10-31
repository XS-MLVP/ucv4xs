"""Adversarial actual packets must fail before any checked coverage credit."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from toffee import Scoreboard
from suites.frontend.bpu.bpu.checker.selective_learning import Checks
from suites.frontend.bpu.bpu.coverage.selective_learning import Coverage
from suites.frontend.bpu.bpu.model.tage.selective_learning import ALL_PROGRAMS as PROGRAMS, LATER_PROGRAMS
from tests.bpu.scoreboard.test_selective_learning import foundation
from tests.bpu.scoreboard.test_direction_forwarding import resolution


def fixture(program):
    model, event, anchor, originals = deepcopy(foundation(program.capacity, program.direction))
    pipeline = NS(model=model, board=Scoreboard('selective-learning-negative-controls'), last_tick=1000,
        source_token=lambda s: s.token, raise_failure=lambda: None, retire_source=lambda tick: None)
    checks = Checks(pipeline, Coverage(program), program)
    sources = tuple(NS(token=t, prediction_tick=100+10*i, meta_tick=104+10*i,
        meta={'original': i}) for i, t in enumerate(originals))
    checks.arm(sources)
    checks.begin_read_window()
    checks.begin_batch(program.first_batch)
    return checks


def packet(checks, *, offer=True):
    records = tuple(tuple(dict(shadow=1, **checks.keys[h][owner], counter=checks.program.initial[owner])
        for h in range(len(checks.program.paths))) + tuple(dict(shadow=0, row=0, valid=0, tag=0, counter=0)
            for _ in range(4-len(checks.program.paths))) for owner in range(2))
    return dict(records=records, state=dict(reset=0,
        reads=({'valid': 1, 'mask': 1}, {'valid': 0, 'mask': 0}),
        training={'valid': 0, 'ready': 1}, prediction={'valid': 1, 'ready': 1},
        dirty=((0,)*4, (0,)*4),
        incoming=tuple({'valid': int(offer and owner == checks.program.active),
            'bits': dict(checks.keys[0][owner], counter=checks.program.proposal) if owner == checks.program.active else {}}
            for owner in range(2)),
        writes=({'valid': 0, 'ready': 0, 'bits': {}}, {'valid': 0, 'ready': 0, 'bits': {}})))


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
def test_valid_partial_proposal_is_not_itself_a_checked_function(program):
    checks = fixture(program)
    checks.capture_state(NS(tick=1000), packet(checks))
    checks.raise_failure()
    assert len(checks.offers) == 1 and checks.counts[0] == 1
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
@pytest.mark.parametrize('fault', ('companion-write', 'wrong-proposal', 'wrong-current',
    'wrong-original-destination', 'reset', 'unblocked-service', 'read-interrupted', 'reread'))
def test_qualified_proposal_cannot_hide_inactive_companion_or_changed_owner(program, fault):
    checks = fixture(program)
    actual = packet(checks)
    row = actual['state']
    active = program.active
    if fault == 'companion-write': row['incoming'][1-active]['valid'] = 1
    elif fault == 'wrong-proposal': row['incoming'][active]['bits']['counter'] = 0
    elif fault == 'wrong-current': actual['records'][active][0]['counter'] = 7
    elif fault == 'wrong-original-destination': row['incoming'][active]['bits']['tag'] ^= 1
    elif fault == 'reset': row['reset'] = 1
    elif fault == 'unblocked-service': row['writes'][active]['ready'] = 1
    elif fault == 'read-interrupted': row['reads'][0]['valid'] = 0
    elif fault == 'reread': row['reads'][1]['valid'] = 1
    checks.capture_state(NS(tick=1000), actual)
    with pytest.raises(AssertionError) as first: checks.raise_failure()
    with pytest.raises(AssertionError) as second: checks.finish()
    assert first.value is second.value
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('fault', ('extra-companion', 'wrong-payload', 'duplicate', 'before-release'))
def test_exact_services_cannot_be_replaced_by_final_counter_equality(fault):
    checks = fixture(PROGRAMS[0])
    expected = dict(checks.keys[0][0], counter=1)
    checks.wave_plan = ((expected,), ())
    checks.release_tick = 1000
    receipt = NS(accepted_tick=1002, value=deepcopy(expected))
    owner = 0
    if fault == 'extra-companion': owner = 1
    elif fault == 'wrong-payload': receipt.value['counter'] = 2
    elif fault == 'duplicate': checks.write_accepted(owner, receipt)
    elif fault == 'before-release': checks.release_tick = None
    with pytest.raises(AssertionError): checks.write_accepted(owner, receipt)
    assert checks.coverage.groups['checked'].coverage == 0


def test_duplicate_original_receipts_fail_before_input_credit():
    checks = fixture(PROGRAMS[0])
    sources = checks.sources
    checks.sources = ()
    with pytest.raises(AssertionError): checks.arm((sources[0],)*len(sources))
    assert checks.coverage.groups['checked'].coverage == 0


def test_clean_unreferenced_cache_records_need_not_remain_allocated():
    checks = fixture(PROGRAMS[0])
    actual = packet(checks)
    for owner in actual['records']:
        for record in owner: record['shadow'] = 0
    checks.capture_state(NS(tick=1000), actual)
    checks.raise_failure()
    assert len(checks.offers) == 1
    assert checks.coverage.groups['checked'].coverage == 0


def test_missing_already_learned_identity_cannot_use_a_clean_cache_exception():
    checks = fixture(PROGRAMS[0])
    checks.counts[0] = 2
    actual = packet(checks)
    actual['records'][0][0]['shadow'] = 0
    checks.capture_state(NS(tick=1000), actual)
    with pytest.raises(AssertionError): checks.raise_failure()
    assert checks.coverage.groups['checked'].coverage == 0


def test_actual_acceptances_do_not_replace_a_missing_qualified_proposal():
    checks = fixture(PROGRAMS[0])
    events = []
    for ordinal, index in enumerate(checks.batch):
        tick = 1000+2*ordinal
        actual = packet(checks, offer=False)
        actual['state']['training']['valid'] = 1
        checks.capture_state(NS(tick=tick), actual)
        events.append((tick, resolution(checks.sources[index].token, checks.program.outcome)))
    checks.pipeline.last_resolution_controls = events[-1][0], (False, False, True, True, False, False, False)
    checks.accepted_burst(tuple(events))
    with pytest.raises(AssertionError): checks.pending()
    assert checks.coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program', LATER_PROGRAMS, ids=lambda p: p.name)
def test_reverse_later_learning_cannot_omit_its_actual_NT_prefix(program):
    checks = fixture(program)
    source = checks.sources[0]
    malformed = resolution(source.token, ((1, False, True),))
    after = NS(prediction_tick=1100, meta_tick=1104)
    with pytest.raises(AssertionError, match='complete actually executed NT prefix'):
        checks.recovered(((source, (1000, malformed), after), (source, (1010, malformed), after)), ())
    assert checks.coverage.groups['checked'].coverage == 0
