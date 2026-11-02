"""The current PHR ABI has a physical value, never a synthesized flag/echo."""
from copy import deepcopy

import pytest
from toffee import Bundle, Scoreboard

from suites.frontend.bpu.bpu.bundle.ports import metadata_with_phr, validate_training_geometry
from suites.frontend.bpu.bpu.checker.phr.association import BpuPhrAssociation
from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.model.phr.model import BpuPhrReference, LENGTH, LAYOUT, subtract
from suites.frontend.bpu.bpu.transaction.types import BpuRedirect
from tests.framework.fakes import Signal, event

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('value', range(LENGTH))
@pytest.mark.parametrize('taken', (0, 1))
def test_value_only_ring_arithmetic_checks_every_physical_position(value, taken):
    assert subtract({'value': value}, 2 * taken) == {'value': (value - 2 * taken) % LENGTH}


def test_physical_reference_never_creates_an_unobservable_pointer_flag():
    reference = BpuPhrReference(pointer_flags=False)
    assert reference.state['pointer'] == reference.state['s1_pointer'] == {'value': 0}
    assert reference.meta2['pointer'] == reference.meta3['pointer'] == {'value': 0}
    assert len(reference.state['cells']) == 532 and len(reference.state['fold1']) == len(LAYOUT) == 33


def phr_node(*, direction='input', width=10, extra=False):
    leaves = dict(phrPtr_value=Signal(530, width=width, direction=direction),
                  phrLowBits=Signal(7, width=13, direction=direction))
    if extra:
        leaves['phrPtr_flag'] = Signal(direction=direction)
    return Bundle(phr=Bundle(**leaves), other=Signal(1, direction=direction))


def test_logical_metadata_drives_only_the_actual_value_and_low_bits():
    physical = phr_node()
    logical = metadata_with_phr(physical, direction='input')
    assert set(logical.phr.phrPtr) == {'value'}
    logical.drive(dict(phr=dict(phrPtr=dict(value=2), phrLowBits=9), other=0))
    assert physical.phr.phrPtr_value.U() == 2 and physical.phr.phrLowBits.U() == 9
    with pytest.raises(ValueError):
        logical.drive(dict(phr=dict(phrPtr=dict(value=2, flag=1), phrLowBits=9), other=0))


@pytest.mark.parametrize('fault', ('flag', 'width', 'direction'))
def test_changed_phr_projection_requires_migration_not_silent_truncation(fault):
    physical = phr_node(extra=fault == 'flag', width=9 if fault == 'width' else 10,
                        direction='output' if fault == 'direction' else 'input')
    with pytest.raises(ValueError, match='fields|width|direction'):
        metadata_with_phr(physical, direction='input')


@pytest.mark.parametrize('field,bad', (
    ('value', -1), ('value', LENGTH), ('value', 1023), ('value', True), ('value', 1.0),
    ('phrLowBits', -1), ('phrLowBits', 1 << 13), ('phrLowBits', True), ('phrLowBits', 1.0)))
def test_recovery_rejects_nonphysical_phr_before_driver_admission(field, bad):
    metadata = dict(phr=dict(phrPtr=dict(value=0), phrLowBits=0))
    if field == 'value':
        metadata['phr']['phrPtr']['value'] = bad
    else:
        metadata['phr'][field] = bad
    with pytest.raises(ValueError, match='PHR'):
        BpuRedirect(0x4000, metadata).payload()


def test_only_the_declared_output_only_ras_address_is_projected_from_recovery():
    metadata = dict(phr=dict(phrPtr=dict(value=531), phrLowBits=8191),
                    ras=dict(ssp=3, topRetAddr_addr=0x8000, unexpected=7))
    payload = BpuRedirect(0x4000, metadata).payload()
    assert payload['meta']['ras'] == dict(ssp=3, unexpected=7)
    assert metadata['ras']['topRetAddr_addr'] == 0x8000
    assert payload['meta']['phr'] == metadata['phr']


def test_missing_or_fabricated_flag_metadata_is_not_a_current_checkpoint():
    for pointer in ({'flag': 0, 'value': 0}, {}, {'value': 0, 'unknown': 1}):
        with pytest.raises(ValueError, match='value-only'):
            BpuRedirect(0x4000, dict(phr=dict(phrPtr=pointer, phrLowBits=0))).payload()


@pytest.mark.parametrize('shape', ((1, 1, 2), (2, 2, 2), (1, 1, 1), (1, 2, 2), (1, 1)))
def test_training_geometry_keeps_main_successor_but_rejects_fabricated_or_missing_pcs(shape):
    pcs = tuple(tuple(Bundle(addr=Signal(width=49)) for _ in range(size)) for size in shape)
    if shape == (1, 1, 2):
        validate_training_geometry(pcs)
    else:
        with pytest.raises(ValueError, match='projection'):
            validate_training_geometry(pcs)


def row(*, s1=0, s2=0, s3=0, low=0, reset=0):
    pointer = {'value': 0}
    return dict(reset=reset,
        pipeline=dict(s1_valid=s1, s2_valid=s2, s3_valid=s3, s1_flush=0, s2_flush=0),
        boundary=dict(fire1=s1, fire2=s2, redirect=dict(valid=0), s2=dict(valid=0), s3=dict(valid=0)),
        parent=dict(s1_pc=0x4000, s1_taken=0, s1_position=31, s3_pc=0x4000),
        public_prediction=dict(valid=s1, ready=s1,
            bits=dict(start_pc=0x4000, taken=0, position=31, s2_override=0, s3_override=0)),
        public_meta=dict(valid=s3, bits=dict(resolve={}, redirect=dict(phr=dict(phrPtr=pointer, phrLowBits=low)))),
        phr_meta=dict(pointer=deepcopy(pointer), low=low))


def pair():
    association = BpuPhrAssociation()
    board = Scoreboard('phr.value-only-lineage')
    check = lambda expected, actual: board.check(expected=expected, actual=actual)
    return association, check


def test_equal_payloads_still_have_distinct_input_uids_without_fake_target_or_perf():
    association, check = pair()
    for tick, sample in enumerate((row(s1=1), row(s1=1, s2=1), row(s2=1, s3=1), row(s3=1)), 1):
        association.observe(sample, tick * 2, check)
    first, second = association.completed
    assert first.uid != second.uid and first.epoch == second.epoch
    assert first.prediction == second.prediction and first.meta == second.meta
    assert first.prediction.target is None and first.meta.perf is None
    assert first.prediction_tick == 2 and second.prediction_tick == 4
    association.finish(check)


@pytest.mark.parametrize('fault', ('missing-valid', 'wrong-low', 'wrong-pointer', 'wrong-pc'))
def test_input_uid_lineage_rejects_missing_or_misbound_s3(fault):
    association, check = pair()
    association.observe(row(s1=1), 2, check)
    association.observe(row(s2=1), 4, check)
    sample = row(s3=1)
    if fault == 'missing-valid':
        sample['public_meta']['valid'] = 0
    elif fault == 'wrong-low':
        sample['public_meta']['bits']['redirect']['phr']['phrLowBits'] = 1
    elif fault == 'wrong-pointer':
        sample['public_meta']['bits']['redirect']['phr']['phrPtr']['value'] = 2
    else:
        sample['parent']['s3_pc'] += 32
    with pytest.raises(AssertionError):
        association.observe(sample, 6, check)
    with pytest.raises(AssertionError):
        association.finish(check)


def test_reset_cancels_named_input_but_does_not_reuse_its_uid():
    association, check = pair()
    association.observe(row(s1=1), 2, check)
    old_uid = association.stage2['uid']
    with pytest.raises(AssertionError):
        association.finish(check)
    association.observe(row(reset=1), 4, check)
    association.observe(row(s1=1), 6, check)
    assert association.stage2['uid'] > old_uid
    assert association.cancellations == [dict(uid=old_uid, epoch=0, tick=4, reason='reset')]
    association.observe(row(s2=1), 8, check)
    association.observe(row(s3=1), 10, check)
    association.finish(check)


def test_same_total_without_exact_terminal_uid_history_cannot_finish():
    association, check = pair()
    association.observe(row(s1=1), 2, check)
    association.observe(row(s2=1), 4, check)
    association.observe(row(s3=1), 6, check)
    # Checker-layer corruption only: keep counts but rebind a receipt to an
    # unknown owner. This is not a hardware tag or a mutation of model state.
    association._completions[0] = (99, 0, 6)
    with pytest.raises(AssertionError):
        association.finish(check)


def test_corrupted_physical_history_is_latched_before_it_can_seed_lineage():
    checker = BpuPhrChecker(scope='value-only-corruption')
    checker.initialized = True
    before = deepcopy(checker.reference.state)
    sample = row()
    sample.update(state=deepcopy(before), phr_meta=dict(pointer=dict(value=0), low=0))
    sample['state']['cells'][-1] = 1
    checker.capture(type('Observation', (), dict(value=sample, event=event(2)))())
    assert checker.reference.state == before and checker.association.accepted == 0
    with pytest.raises(AssertionError) as caught:
        checker.finish()
    assert caught.value is checker.failure
