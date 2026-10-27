"""Pure RVV v1.0 oracle qualification; no DUT or Chisel-derived model."""
import pytest

from vagqverify.vagq.isa_reference import (
    access_order_is_legal,
    architectural_accesses,
    allowed_destination_values,
    classify_elements,
    completed_before_fault,
    destination_value_is_legal,
    emul_encoding,
    flow_fragments,
    restart_accesses,
    validate_vector_configuration,
    vlmax,
)


pytestmark = pytest.mark.toffee_functional_coverage(False)


@pytest.mark.parametrize(
    "vsew,vlmul,expected",
    [
        (0, 5, 2),  # VLEN=128, e8, mf8
        (0, 6, 4),  # e8, mf4
        (0, 7, 8),  # e8, mf2
        (0, 0, 16),
        (1, 1, 16),
        (2, 2, 16),
        (3, 3, 16),
    ],
)
def test_vlmax_uses_fractional_lmul_without_rounding(vsew, vlmul, expected):
    assert vlmax(vsew=vsew, vlmul=vlmul) == expected
    validate_vector_configuration(
        vsew=vsew, vlmul=vlmul, vl=expected, vstart=0,
    )


def test_element_classes_are_disjoint_and_vstart_ge_vl_has_no_body():
    states = classify_elements(vl=3, vstart=1, vlmax_value=8, mask=0b101)
    assert [item.kind for item in states] == [
        "prestart", "inactive", "active", "tail", "tail", "tail", "tail", "tail",
    ]
    no_body = classify_elements(vl=3, vstart=3, vlmax_value=8, mask=0xff)
    assert {item.kind for item in no_body[:3]} == {"prestart"}
    assert all(item.kind == "tail" for item in no_body[3:])


def test_emul_encoding_is_derived_from_sew_lmul_and_operand_eew():
    # LMUL=mf2, SEW=32, data EEW=64 => EMUL=1.
    assert emul_encoding(vsew=2, vlmul=7, eew=3) == 0
    # LMUL=m2, SEW=32, index EEW=8 => index EMUL=mf2.
    assert emul_encoding(vsew=2, vlmul=1, eew=0) == 7


def test_strided_negative_address_and_indexed_zero_extension_are_architectural():
    strided = architectural_accesses(
        kind="strided", base=0x1000, vsew=0, vlmul=0, vl=3, vstart=0,
        mask=0x7, data_eew=0, stride=(1 << 64) - 4,
    )
    assert [access.address for access in strided] == [0x1000, 0xffc, 0xff8]

    indexed = architectural_accesses(
        kind="indexed", base=0x2000, vsew=0, vlmul=0, vl=2, vstart=0,
        mask=0x3, data_eew=0, index_eew=1,
        index_data=0x8000 | (0x12 << 16),
    )
    assert [access.address for access in indexed] == [0xa000, 0x2012]


def test_segment_accesses_share_element_base_and_increment_only_field():
    accesses = architectural_accesses(
        kind="strided", base=0x4000, vsew=2, vlmul=0, vl=2, vstart=0,
        mask=0x3, data_eew=2, nf=2, stride=0x20,
    )
    assert [(item.element, item.field, item.address) for item in accesses] == [
        (0, 0, 0x4000), (0, 1, 0x4004), (0, 2, 0x4008),
        (1, 0, 0x4020), (1, 1, 0x4024), (1, 2, 0x4028),
    ]


def test_flow_partition_has_no_gap_or_duplicate_for_wide_segment_elements():
    fragments = []
    # Five 32-bit fields occupy 20 bytes per segment element and therefore
    # cross the 16-byte public flow boundary.
    for uop_idx in range(4):
        fragments.extend(flow_fragments(
            vsew=2, vlmul=0, vl=3, vstart=0, mask=0x7,
            data_eew=2, nf=4, uop_idx=uop_idx, active_only=True,
        ))
    covered = {
        (item.element, item.field, item.flow * 16 + byte)
        for item in fragments
        for byte in range(item.byte_offset, item.byte_offset + item.width)
    }
    expected = {
        (element, field, byte)
        for element in range(3)
        for field in range(5)
        for byte in range(element * 20 + field * 4, element * 20 + field * 4 + 4)
    }
    assert covered == expected
    assert sum(item.width for item in fragments) == len(expected)


def test_ordered_segment_allows_field_reordering_but_not_element_reordering():
    accesses = architectural_accesses(
        kind="indexed", base=0x5000, vsew=0, vlmul=0, vl=2, vstart=0,
        mask=0x3, data_eew=0, nf=1, index_eew=0, index_data=0x20 | (0x40 << 8),
        ordered=True,
    )
    fields_reordered = (accesses[1], accesses[0], accesses[2], accesses[3])
    elements_reordered = (accesses[2], accesses[3], accesses[0], accesses[1])
    assert access_order_is_legal(
        fields_reordered, ordered=True, segmented=True,
    )
    assert not access_order_is_legal(
        elements_reordered, ordered=True, segmented=True,
    )
    assert access_order_is_legal(elements_reordered, ordered=False)


def test_precise_restart_is_suffix_and_prior_accesses_are_prefix():
    accesses = architectural_accesses(
        kind="indexed", base=0x6000, vsew=0, vlmul=0, vl=4, vstart=0,
        mask=0xf, data_eew=0, index_eew=0,
        index_data=0x10 | (0x20 << 8) | (0x30 << 16) | (0x40 << 24),
        ordered=True,
    )
    assert [item.element for item in completed_before_fault(accesses, fault_element=2)] == [0, 1]
    assert [item.element for item in restart_accesses(accesses, fault_element=2)] == [2, 3]


def test_agnostic_results_are_an_allowed_set_not_a_single_value():
    old = 0x12
    computed = 0x34
    assert allowed_destination_values(
        old=old, computed=computed, state="inactive", element_bits=8,
        vma=1, vta=0, vstart=0, vl=4,
    ) == frozenset((0x12, 0xff))
    assert destination_value_is_legal(
        value=0xff, old=old, computed=computed, state="tail", element_bits=8,
        vma=0, vta=1, vstart=0, vl=4,
    )
    # vstart >= vl suppresses agnostic tail updates.
    assert allowed_destination_values(
        old=old, computed=computed, state="tail", element_bits=8,
        vma=0, vta=1, vstart=4, vl=4,
    ) == frozenset((old,))


def test_normative_oracle_sweeps_all_supported_type_and_segment_shapes():
    """Exercise every whole-element VLEN=128 type in the pure oracle.

    This deliberately checks architectural access sets rather than VAGQ's
    current table.  The index vector is supplied as a full element sequence so
    LMUL>1 does not accidentally wrap back to the first 128-bit flow.
    """
    checked = 0
    for vsew in range(4):
        for vlmul in (5, 6, 7, 0, 1, 2, 3):
            try:
                maximum = vlmax(vsew=vsew, vlmul=vlmul)
                # Both data EEW and index EEW must be representable by the
                # three-bit EMUL field exposed by the VAGQ contract.
                for data_eew in range(4):
                    emul_encoding(vsew=vsew, vlmul=vlmul, eew=data_eew)
                    for index_eew in range(4):
                        emul_encoding(vsew=vsew, vlmul=vlmul, eew=index_eew)
                        for nf in range(8):
                            accesses = architectural_accesses(
                                kind="indexed",
                                base=0x100000,
                                vsew=vsew,
                                vlmul=vlmul,
                                vl=maximum,
                                vstart=0,
                                mask=(1 << maximum) - 1,
                                data_eew=data_eew,
                                nf=nf,
                                index_values=tuple(
                                    (index * 0x100) & ((1 << 64) - 1)
                                    for index in range(maximum)
                                ),
                                index_eew=index_eew,
                            )
                            assert len(accesses) == maximum * (nf + 1)
                            assert {item.element for item in accesses} == set(range(maximum))
                            assert {item.field for item in accesses} == set(range(nf + 1))
                            checked += 1
            except ValueError:
                # Reserved/non-representable EMUL combinations are outside
                # the VAGQ public operand domain and are not silently counted.
                continue
    assert checked > 100


def test_vstart_and_mask_partition_is_preserved_for_every_supported_vl():
    for vsew in range(4):
        for vlmul in (5, 6, 7, 0, 1, 2, 3):
            try:
                maximum = vlmax(vsew=vsew, vlmul=vlmul)
            except ValueError:
                continue
            for vl in (0, 1, maximum // 2, maximum):
                if vl > maximum:
                    continue
                for vstart in (0, min(1, maximum), vl, maximum):
                    states = classify_elements(
                        vl=vl, vstart=vstart, vlmax_value=maximum,
                        mask=(1 << maximum) - 1,
                    )
                    assert len(states) == maximum
                    assert sum(item.kind == "active" for item in states) == (
                        max(0, vl - vstart) if vstart < vl else 0
                    )
                    assert sum(item.kind == "prestart" for item in states) == min(
                        vstart, maximum,
                    )
