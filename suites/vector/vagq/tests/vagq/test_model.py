"""Top-level semantic qualification without DUT coverage credit."""

import pytest

from suites.vector.vagq.legacy_pins import P
from suites.vector.vagq.vagq.model import IntegrationModel, _data_size, _slot_element
from suites.vector.vagq.vagq.types import AddrPacket, Beat, DataPacket

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_separate_address_and_data_are_modeled_as_one_entry_plan():
    addr = AddrPacket(entry_idx=2, rob_value=12, base_addr=0x4000,
                      v0_byte_mask=1, vl=1)
    data = DataPacket(entry_idx=2, rob_value=12, op2_data=0x20)
    plan = IntegrationModel.make_plan(addr, data)
    assert plan.active[0]['elem_idx'] == 0
    assert plan.active[0]['vaddr'] == 0x4000
    assert plan.empty == set(range(1, 16))


def test_indexed_address_uses_the_element_width_selected_by_ieew():
    addr = AddrPacket(entry_idx=1, uop_type=4, rob_value=9, base_addr=0x1000,
                      v0_byte_mask=0x3, vl=2, ieew=0)
    indices = 0x22 | (0x44 << 8)
    plan = IntegrationModel.make_plan(addr, DataPacket(1, 0, 9, indices))
    assert plan.active[0]['vaddr'] == 0x1022
    assert plan.active[1]['vaddr'] == 0x1044


def test_exception_and_retry_state_are_external_bitmap_properties():
    addr = AddrPacket(entry_idx=0, uop_type=0, rob_value=3, v0_byte_mask=1, vl=1)
    plan = IntegrationModel.make_plan(addr, DataPacket(0, 0, 3, 0))
    plan.acknowledged = plan.valid_mask
    plan.exception = True
    plan.exception_number = 7
    plan.fault_elem_idx = 0
    assert plan.complete
    assert plan.exception and plan.exception_number == 7


def _fractional_model():
    addr = AddrPacket(entry_idx=0, rob_value=9, base_addr=0x4000,
                      v0_byte_mask=0xffff, vl=2, emul=5, vlmul=5, lq_value=32)
    data = DataPacket(entry_idx=0, rob_value=9, op2_data=8)
    model = IntegrationModel()
    model.admit(addr, data)
    return model


def _empty_output(**changes):
    fields = dict(valid=1, bits_entryIdx=0, bits_issueMask=1 << 2,
                  bits_robIdx_flag=0, bits_robIdx_value=9,
                  bits_isLoad=1, bits_lqIdx_value=34)
    fields.update(changes)
    return {P.p_lsqEmptyReq_0_ + key: value for key, value in fields.items()}


def test_fractional_padding_is_required_cleanup_not_extra_memory():
    model = _fractional_model()
    plan = model.plans[0]
    assert set(plan.active) == {0, 1}
    assert plan.empty == set(range(2, 16))
    assert plan.valid_mask == 0xffff
    plan.acknowledged = 0x3  # Active memory responses alone are insufficient.
    assert not plan.complete
    plan.acknowledged = 0xffff
    assert plan.complete
    assert model._empty_event(_empty_output(), Beat(), 0) == 1 << 2


@pytest.mark.parametrize('changes', (
    {'bits_issueMask': 0}, {'bits_issueMask': 1},
    {'bits_issueMask': (1 << 2) | (1 << 3)}, {'bits_issueMask': 1 << 16},
    {'bits_robIdx_value': 10}, {'bits_robIdx_flag': 1},
    {'bits_isLoad': 0}, {'bits_lqIdx_value': 35},
))
def test_checker_rejects_bad_cleanup_mask_owner_or_slot(changes):
    # Removing the old false alarm must not turn empty markers into don't-care.
    with pytest.raises(AssertionError, match='empty request'):
        _fractional_model()._empty_event(_empty_output(**changes), Beat(), 0)


def test_checker_still_rejects_duplicate_cleanup():
    model = _fractional_model()
    model._empty_event(_empty_output(), Beat(), 0)
    with pytest.raises(AssertionError, match='emitted twice'):
        model._empty_event(_empty_output(), Beat(), 0)


def test_checker_rejects_a_real_read_from_fractional_padding():
    output = {
        P.p_lduReq_0_valid: 1, P.p_lduReq_0_bits_meta_valid: 1,
        P.p_lduReq_0_bits_meta_entryIdx: 0,
        P.p_lduReq_0_bits_meta_byteOffset: 2,
    }
    with pytest.raises(AssertionError, match='non-active byte 2'):
        _fractional_model()._active_event(output, Beat(), 'lduReq', 0)


def test_checker_rejects_writeback_before_reserved_slots_are_released():
    model = _fractional_model()
    model.plans[0].acknowledged = 0x3
    with pytest.raises(AssertionError, match='before all required work completed'):
        model.validate({
            P.p_robWriteback_valid: 1, P.p_robWriteback_bits_entryIdx: 0,
            P.p_robWriteback_bits_robIdx_value: 9,
        }, Beat())


def test_top_model_does_not_share_the_rtl_nonzero_first_site_error():
    addr = AddrPacket(nf=4, deew=2, ieew=3)
    info = dict(elemBase=2, startByteOffset=8, startFieldOffset=0)
    assert _slot_element(addr, info, 8) == 2


def test_top_model_special_layout_stride_is_not_segment_memory_width():
    addr = AddrPacket(nf=6, deew=0, ieew=2)
    info = dict(elemBase=0, startByteOffset=0, startFieldOffset=0)
    assert [_slot_element(addr, info, site) for site in (0, 4, 8, 12)] == [0, 1, 2, 3]


@pytest.mark.parametrize('width,encoding', ((1, 0), (2, 1), (3, 2), (4, 2),
    (6, 3), (8, 3), (10, 4), (12, 4), (16, 4), (24, 4), (40, 4), (64, 4)))
def test_request_size_rounds_up_to_contain_bytes_and_saturates_at_one_flow(width, encoding):
    assert _data_size(width) == encoding
