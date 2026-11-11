"""New-baseline input contracts; these controls do not claim RTL credit."""
from copy import deepcopy

import pytest

from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect
from suites.frontend.bpu.testbenches.ras.env.driver.encoding import encode_cfi_pc
from suites.frontend.bpu.testbenches.mbtb.env.bundle.abi import expected_schema
from suites.frontend.bpu.testbenches.mbtb.env.bundle.abi import validate_schema
from suites.frontend.bpu.testbenches.mbtb.env.driver.feedback import expected_mbtb_feedback
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBatchTraining
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBranchFeedback
from suites.frontend.bpu.testbenches.shared.env.bundle.guarded_redirect import validate_guarded_cfi
from suites.frontend.bpu.testbenches.shared.tests.framework.fakes import Signal

pytestmark = pytest.mark.selftest


@pytest.mark.parametrize('width,direction', ((49, 'input'), (51, 'input'), (50, 'output')))
def test_missing_guard_or_wrong_direction_is_rejected_even_if_live_values_fit(width, direction):
    validate_guarded_cfi(Signal(width=50, direction='input'))
    with pytest.raises(ValueError):
        validate_guarded_cfi(Signal(width=width, direction=direction))


@pytest.mark.parametrize('pc', (0, (1 << 48) + 3, (1 << 49) + 3, (1 << 50) - 1))
def test_redirect_preserves_the_actual_guard_independently_of_virtual_sign(pc):
    assert BpuRedirect(pc, {}).payload()['cfi_pc'] == pc
    assert BpuRedirect(0x4000, {}, cfi_pc=pc).payload()['cfi_pc'] == pc


@pytest.mark.parametrize('pc', (0, (1 << 49) + 6, (1 << 50) + 6, (1 << 51) - 2))
def test_ras_guarded_byte_address_only_loses_the_fixed_alignment_bit(pc):
    assert encode_cfi_pc(pc) == pc // 2


@pytest.mark.parametrize('pc', (True, -2, 3, 1 << 51))
def test_ras_guarded_address_domain_remains_strict(pc):
    with pytest.raises(ValueError):
        encode_cfi_pc(pc)


def metadata():
    return tuple(tuple(dict(rawHit=0, position=0, counter_value=0,
        **({'attribute': dict(branchType=0, rasAction=0)} if way < 4 else {}))
        for way in range(5)) for _ in range(2))


def test_training_victim_projection_drives_only_the_two_consumed_fields():
    values = metadata()
    values[1][4].update(rawHit=1, position=23, counter_value=3)
    tx = MbtbBatchTraining(0x4000, values,
        (MbtbBranchFeedback(0x6000, 1, 23, 3, mispredict=1),))
    before = deepcopy(tx.meta_entries)
    wire = expected_mbtb_feedback(tx)['meta_entries']
    assert len(wire[1]) == 5
    assert wire[1][4] == dict(rawHit=1, position=23)
    assert tx.meta_entries == before
    assert 'counter_value' not in wire[1][4] and 'attribute' not in wire[1][4]


def test_missing_training_victim_is_not_silently_reinterpreted_as_a_miss():
    with pytest.raises(ValueError):
        MbtbBatchTraining(0, tuple(row[:4] for row in metadata()),
            (MbtbBranchFeedback(0x6000, 1, 23, 3, mispredict=1),))


def test_new_abi_requires_both_victim_fields_but_no_fabricated_payload():
    schema = expected_schema()
    for align in range(2):
        base = f'training.meta_entries[{align}][4].'
        assert schema[base + 'rawHit'] == 1 and schema[base + 'position'] == 5
        assert base + 'counter_value' not in schema
        broken = {k: v for k, v in schema.items() if k != base + 'position'}
        with pytest.raises(ValueError):
            validate_schema(broken)
