"""Hand-derived, exhaustive pointer and bit-basis checks for the independent model."""
from bpuverify.common.model.configuration import *
from copy import deepcopy
from itertools import product

import pytest

from bpuverify.bpu.model.phr.model import BpuPhrReference
from bpuverify.bpu.model.phr.model import LAYOUT
from bpuverify.bpu.model.phr.model import MASK
from bpuverify.bpu.model.phr.model import fold
from bpuverify.bpu.model.phr.model import folds
from bpuverify.bpu.model.phr.model import path_hash
from bpuverify.bpu.model.phr.model import subtract


def boundary():
    meta = dict(pointer=dict(flag=0, value=0), low=0)
    return dict(stall=0, fire0=0, fire1=0, fire2=0,
        redirect=dict(valid=0, taken=0, cfi_pc=0, target=0, meta=deepcopy(meta)),
        **{stage: dict(valid=0, start_pc=0, prediction=dict(taken=0, position=0, target=0),
            meta=deepcopy(meta)) for stage in ('s1', 's2', 's3')})


@pytest.mark.parametrize('value,flag,taken', tuple(product(range(PHR_STORAGE_BITS), (0, 1), (0, 1))))
def test_pointer_subtraction_and_flag(value, flag, taken):
    wanted_value = value - 2 if taken and value >= 2 else value + PHR_STORAGE_BITS - 2 if taken else value
    wanted_flag = 1 - flag if taken and value < 2 else flag
    assert subtract(dict(value=value, flag=flag), 2 * taken) == dict(value=wanted_value, flag=wanted_flag)


@pytest.mark.parametrize('length,width', LAYOUT)
def test_all_fold_bit_bases(length, width):
    for bit in range(PHR_STORAGE_BITS):
        assert fold(1 << bit, length, width) == (1 << (bit % width) if bit < length else 0)
    assert fold(MASK, length, width) == sum(((length // width + int(index < length % width)) % 2) << index
        for index in range(width))


@pytest.mark.parametrize('pointer', range(PHR_STORAGE_BITS))
def test_all_physical_rotations_and_pending_overlay(pointer):
    model = BpuPhrReference()
    model.state['pointer']['value'] = pointer
    for cell in range(PHR_STORAGE_BITS):
        model.state['cells'] = [int(index == cell) for index in range(PHR_STORAGE_BITS)]
        assert model.physical_read(model.state['pointer']) == 1 << ((cell - pointer - 1) % PHR_STORAGE_BITS)
    model.state['cells'] = [1] * PHR_STORAGE_BITS
    for taken, low, shift in product((0, 1), (0, 0x1800, 0x1FFF), range(4)):
        model.state['pending'] = dict(valid=1, taken=taken, low=low, shift=shift)
        width = 15 if taken else 13
        wanted_low = low * 4 + shift if taken else low
        assert model.logical() == ((MASK >> width) << width) | wanted_low


@pytest.mark.parametrize('pc,target,wanted', [(0, 0, 0), (0x101, 0x4000, 0x3010),
    (0x1FF, 0, 0x1FF0), (0x200, 2, 1), (0x1FF, 0xFFFF, 0x600F)])
def test_hash_fixed_vectors(pc, target, wanted):
    assert path_hash(pc, target) == wanted


def test_s1_consumes_all_fifteen_pending_bits():
    model = BpuPhrReference()
    model.state['pending'] = dict(valid=1, taken=1, low=0x1800, shift=0)
    row = boundary()
    row['fire0'] = 1
    row['s1'].update(valid=1, prediction=dict(taken=1, position=0, target=0))
    model.advance(row, 0)
    assert model.state['fold1'] == folds(0x18000)
    assert model.state['pointer'] == dict(value=PHR_STORAGE_BITS - 2, flag=1)


def test_s1_not_taken_does_not_change_current_history():
    model = BpuPhrReference()
    model.state['fold0_reg'] = folds(0x4321)
    model.state['fold1'] = folds(0x1234)
    row = boundary()
    row['s1']['valid'] = 1
    row['fire0'] = 1
    model.advance(row, 0)
    assert model.state['fold0_reg'] == model.state['fold1'] == folds(0x4321)


@pytest.mark.parametrize('valids', tuple(product((0, 1), repeat=4)))
def test_four_source_priority_uses_one_prestate(valids):
    model = BpuPhrReference()
    row = boundary()
    row['fire0'] = 1
    row['redirect'].update(valid=valids[0], taken=1, cfi_pc=0, target=2)
    for stage, valid, target in zip(('s3', 's2', 's1'), valids[1:], (4, 8, 16)):
        row[stage].update(valid=valid, prediction=dict(taken=1, position=0, target=target))
    winning = next((index for index, valid in enumerate(valids) if valid), None)
    model.advance(row, 0)
    assert model.state['fold1'] == folds(0 if winning is None else (1, 2, 4, 8)[winning])
    assert model.state['pending']['valid'] == int(winning in (1, 2, 3))
    if winning == 0:
        assert model.state['cells'][PHR_STORAGE_BITS - 1] == 1


def test_not_taken_restores_metadata_without_shift():
    model = BpuPhrReference()
    model.state['cells'] = [1] * PHR_STORAGE_BITS
    row = boundary()
    row['redirect'].update(valid=1, meta=dict(pointer=dict(value=10, flag=1), low=0x1234))
    model.advance(row, 0)
    assert model.state['pointer'] == dict(value=10, flag=1)
    for bit in range(PHR_STORAGE_BITS):
        assert model.state['cells'][(11 + bit) % PHR_STORAGE_BITS] == ((0x1234 >> bit) & 1 if bit < 13 else 1)
    assert model.state['fold0_reg'] == folds(((MASK >> 13) << 13) | 0x1234)


def test_stall_holds_fold_register_but_not_redirect_restore():
    model = BpuPhrReference()
    row = boundary()
    row['stall'] = 1
    row['redirect'].update(valid=1, taken=1, cfi_pc=0, target=2)
    model.advance(row, 0)
    assert model.state['fold0_reg'] == [0] * len(PHR_FOLDS)
    assert model.state['cells'][PHR_STORAGE_BITS - 1] == 1
    assert model.state['pointer'] == dict(value=PHR_STORAGE_BITS - 2, flag=1)


def test_redirect_replaces_old_pending_write():
    model = BpuPhrReference()
    model.state['pointer'] = dict(value=26, flag=0)
    model.state['pending'] = dict(valid=1, taken=1, low=8191, shift=3)
    row = boundary()
    row['redirect'].update(valid=1, meta=dict(pointer=dict(value=0, flag=0), low=1))
    model.advance(row, 0)
    assert model.state['cells'] == [int(index == 1) for index in range(PHR_STORAGE_BITS)]
    assert model.state['pending']['valid'] == 0


def test_s2_does_not_erase_previous_pending_physical_commit():
    model = BpuPhrReference()
    model.state['pointer'] = dict(value=26, flag=0)
    model.state['pending'] = dict(valid=1, taken=1, low=8191, shift=3)
    row = boundary()
    row['s2'].update(valid=1, prediction=dict(taken=0, position=0, target=0))
    model.advance(row, 0)
    assert model.state['cells'] == [int(index in range(27, 42)) for index in range(PHR_STORAGE_BITS)]
    assert model.state['pending'] == dict(valid=1, taken=0, low=0, shift=0)


def test_pipeline_metadata_causal_check_is_not_optional():
    model = BpuPhrReference()
    row = boundary()
    row['s3']['valid'] = 1
    row['s3']['meta']['low'] = 1
    with pytest.raises(AssertionError, match='pipeline metadata association'):
        model.advance(row, 0)


def test_odd_metadata_is_a_counterexample_to_global_even_waiver():
    model = BpuPhrReference()
    row = boundary()
    row['redirect'].update(valid=1, meta=dict(pointer=dict(value=3, flag=1), low=0))
    model.advance(row, 0)
    assert model.state['pointer'] == dict(value=3, flag=1)


@pytest.mark.parametrize('which', ('flag', 'value'))
def test_invalid_pointer_rejected(which):
    pointer = dict(flag=0, value=0)
    pointer[which] = 2 if which == 'flag' else PHR_STORAGE_BITS
    with pytest.raises(ValueError, match='invalid PHR pointer'):
        subtract(pointer, 2)
