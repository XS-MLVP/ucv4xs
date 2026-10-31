"""Raw MaskGen protocol qualification; architectural policy has separate tests."""
import pytest

from suites.vector.vagq.maskgen.reference import MaskRequest, evaluate_protocol, mop_info

pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_unmasked_non_segment_body_uses_v0_active_bytes():
    request = MaskRequest(0b0101, 0, 0, 0, 4, 0, 0, 0, 0, 0)
    assert evaluate_protocol(request) == {
        'elemValidMask': 0xffff,
        'elemActiveMask': 0x0005,
        'elemAgnosticMask': 0x0000,
        'mergeWriteMask': 0xfffa,
        'elemBase': 0,
        'startFieldOffset': 0,
        'startByteOffset': 0,
        'skipMerge': 0,
    }


def test_vstart_excludes_prefix_and_vta_marks_tail_agnostic():
    request = MaskRequest(0xffff, 0, 0, 0, 5, 2, 0, 1, 0, 0)
    result = evaluate_protocol(request)
    assert result['elemActiveMask'] == 0x001c
    assert result['elemAgnosticMask'] == 0xffe0
    assert result['mergeWriteMask'] == 0xffe3


def test_vma_marks_masked_body_agnostic_without_making_it_active():
    request = MaskRequest(0b0101, 0, 0, 0, 4, 0, 1, 0, 0, 0)
    result = evaluate_protocol(request)
    assert result['elemActiveMask'] == 0x0005
    assert result['elemAgnosticMask'] == 0x000a
    assert result['mergeWriteMask'] == 0xfffa


def test_segment_mask_uses_element_starts_and_keeps_only_active_bytes():
    request = MaskRequest(0x00ff, 0, 0, 0, 4, 0, 0, 0, 0, 1)
    result = evaluate_protocol(request)
    assert result['elemValidMask'] == 0x5555
    assert result['elemActiveMask'] == 0x0055
    assert result['elemAgnosticMask'] == 0
    assert result['mergeWriteMask'] == 0xfff0


def test_info_table_can_skip_a_destination_uop_without_losing_element_metadata():
    request = MaskRequest(0xffff, 0, 2, 0, 16, 0, 0, 0, 2, 1)
    info = mop_info(request)
    assert info.skip_merge is True
    assert (info.first, info.last, info.valid_mask, info.full_mask) == (8, 11, 0x55, 0xff)
    assert evaluate_protocol(request)['skipMerge'] == 1


@pytest.mark.parametrize('deew', range(4))
@pytest.mark.parametrize('nf', (1, 2, 4, 6, 7))
def test_full_segment_fields_share_one_element_window(deew, nf):
    # LMUL=1: each field has a full register of active elements. Moving to
    # another FIELD cannot turn that register into tail/old-vd bytes.
    elements = 16 >> deew
    for uop in range(nf + 1):
        request = MaskRequest(0xFFFF, deew, deew, 0, elements, 0, 0, 0, uop, nf)
        assert mop_info(request).destination_window == 0
        assert evaluate_protocol(request)['mergeWriteMask'] == 0
        assert evaluate_protocol(request)['elemAgnosticMask'] == 0


@pytest.mark.parametrize('emul,windows', ((0, 1), (1, 2), (2, 4)))
@pytest.mark.parametrize('v0', (0, 0xFFFF, 0xA5A5))
@pytest.mark.parametrize('vma,vta', ((0, 0), (0, 1), (1, 0), (1, 1)))
def test_segment_merge_policy_uses_element_not_field_major_register_index(emul, windows, v0, vma, vta):
    # Two e32 fields. Every LMUL window has exactly two destination uops.
    # This byte-by-byte answer does not call the layout/mask implementation.
    vl, vstart = 4 * windows - 1, 1
    for uop in range(2 * windows):
        expected_window = uop // 2
        body = tail = 0
        for byte in range(16):
            element = expected_window * 4 + byte // 4
            if vstart <= element < vl:
                body |= 1 << byte
            elif element >= vstart and element >= vl:
                tail |= 1 << byte
        inactive = body & ~v0 & 0xFFFF
        expected_merge = (~(body & v0)) & 0xFFFF
        expected_agnostic = (inactive if vma else 0) | (tail if vta else 0)
        request = MaskRequest(v0, 2, 2, emul, vl, vstart, vma, vta, uop, 1)
        assert mop_info(request).destination_window == expected_window
        actual = evaluate_protocol(request)
        assert actual['mergeWriteMask'] == expected_merge
        assert actual['elemAgnosticMask'] == expected_agnostic


def test_fractional_fields_preserve_the_same_partial_element_window():
    # Five fields, e16, EMUL=mf4, two active elements => four active bytes
    # in EVERY field's physical register, not just in the first field.
    for uop in range(5):
        request = MaskRequest(0xFFFF, 1, 1, 6, 2, 0, 0, 1, uop, 4)
        assert mop_info(request).destination_window == 0
        result = evaluate_protocol(request)
        assert result['mergeWriteMask'] == 0xFFF0
        assert result['elemAgnosticMask'] == 0xFFF0


def test_skip_merge_keeps_a_later_element_window_instead_of_resetting_to_zero():
    # e8, index e32, two fields, LMUL=2: four uops per element window,
    # of which two have no destination write. Window metadata still advances.
    request = MaskRequest(0xFFFF, 0, 2, 1, 20, 0, 0, 0, 6, 1)
    info = mop_info(request)
    assert info.skip_merge
    assert info.destination_window == 1
    assert evaluate_protocol(request)['mergeWriteMask'] == 0xFFF0


@pytest.mark.parametrize('emul,vl', ((5, 2), (6, 4), (7, 8)))
def test_fractional_layout_reserves_slots_without_making_padding_active(emul, vl):
    # Fixed answers for the allocation protocol; these are not ISA VLMAX values.
    request = MaskRequest(0xffff, 0, 0, emul, vl, 0, 0, 0, 0, 0)
    info = mop_info(request)
    result = evaluate_protocol(request)
    assert (info.first, info.last, info.valid_mask) == (0, 15, 0xffff)
    assert result['elemActiveMask'] == (1 << vl) - 1
    assert result['mergeWriteMask'] == 0xffff ^ ((1 << vl) - 1)
    assert result['elemAgnosticMask'] == 0


def test_legal_vector_layouts_are_bounded_and_reserved_lmul_is_rejected():
    legal = 0
    for emul in range(8):
        for ieew in range(4):
            for deew in range(4):
                for nf in range(8):
                    request = MaskRequest(0xffff, deew, ieew, emul, 16, 0, 0, 0, 0, nf)
                    if request.legal:
                        legal += 1
                        result = evaluate_protocol(request)
                        assert 0 <= result['elemValidMask'] <= 0xffff
                        assert 0 <= result['elemActiveMask'] <= 0xffff
                        assert 0 <= result['elemAgnosticMask'] <= 0xffff
                        assert 0 <= result['mergeWriteMask'] <= 0xffff
    assert legal > 0


@pytest.mark.parametrize('field,value', [
    ('v0_mask', 1 << 16), ('deew', 4), ('ieew', -1), ('emul', 8),
    ('vl', 256), ('vstart', 128), ('uop_idx', 8), ('nf', 8),
])
def test_input_contract_rejects_truncation(field, value):
    values = dict(v0_mask=0, deew=0, ieew=0, emul=0, vl=0, vstart=0,
                  vma=0, vta=0, uop_idx=0, nf=0)
    values[field] = value
    with pytest.raises(ValueError, match=field):
        MaskRequest(**values)
