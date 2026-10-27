"""Architectural reference tests use known register identities, never MOP labels."""
import ast
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from vagqverify.maskgen.architectural import (
    BoundDestination, DestinationBinding, DestinationInstruction, expected_destination,
)
from vagqverify.maskgen.reference import MaskRequest, evaluate, evaluate_protocol
from vagqverify.maskgen.flow_fixture import active_sites, flow_metadata, wide_flow
from vagqverify.qualification.rvv_destination import Instruction as IndependentOracle


pytestmark = pytest.mark.toffee_functional_coverage(False)


def _bound(*, vl=4, vstart=0, mask=0xF, vma=0, vta=0, field=1, register=9, tag=1):
    return BoundDestination(DestinationInstruction(4, Fraction(1), 3, vl, vstart, mask, vma, vta),
                            DestinationBinding(field, register, tag))


def _request(bound):
    p, b = bound.instruction, bound.binding
    oracle = IndependentOracle(p.eew_bytes, p.emul, p.fields, p.vl, p.vstart, p.mask)
    register = next(reg for reg in oracle.registers() if (reg.field, reg.number) == (b.field, b.register_number))
    encoding = {Fraction(1, 8): 5, Fraction(1, 4): 6, Fraction(1, 2): 7,
                Fraction(1): 0, Fraction(2): 1, Fraction(4): 2, Fraction(8): 3}[p.emul]
    return MaskRequest(oracle.expanded_mask(register), p.eew_bytes.bit_length() - 1,
        p.eew_bytes.bit_length() - 1, encoding, p.vl, p.vstart, p.vma, p.vta, b.uop_idx, p.fields - 1)


def test_unbound_architectural_evaluate_fails_instead_of_guessing_identity():
    with pytest.raises(ValueError, match='explicit BoundDestination'):
        evaluate(MaskRequest(0xFFFF, 2, 2, 0, 4, 0, 0, 0, 1, 2))


@pytest.mark.parametrize('vl,start', ((0, 0), (2, 2), (2, 3)))
@pytest.mark.parametrize('vma,vta', ((0, 0), (0, 1), (1, 0), (1, 1)))
def test_reference_no_op_is_correct_without_assuming_any_upstream_gate(vl, start, vma, vta):
    bound = _bound(vl=vl, vstart=start, vma=vma, vta=vta)
    result = evaluate(_request(bound), destination=bound)
    assert result.instruction_executes is False
    assert result.destination_commit_allowed is False
    assert result.memory_elements == ()
    assert (result.active_byte_mask, result.merge_write_mask, result.agnostic_byte_mask) == (0, 0xFFFF, 0)
    oracle = IndependentOracle(4, Fraction(1), 3, vl, start, 0xF)
    register = oracle.registers()[1]
    assert not oracle.check_merge_controls(register, merge_mask=result.merge_write_mask,
        agnostic_mask=result.agnostic_byte_mask, vma=vma, vta=vta)


def test_raw_protocol_no_op_is_not_silently_used_as_the_isa_reference():
    bound = _bound(vl=0, vta=1)
    request = _request(bound)
    assert evaluate_protocol(request)['elemAgnosticMask'] == 0xFFFF
    assert evaluate(request, destination=bound).agnostic_byte_mask == 0


def test_destination_identity_not_uop_number_determines_the_element_window():
    instruction = DestinationInstruction(4, Fraction(2), 2, 7, 1, 0xFF)
    # The input fixture supplies v11: field 1, second register, elements 4..7.
    # Different ownership tags must NOT change this architectural expectation.
    outputs = []
    for tag in (0, 3, 7):
        bound = BoundDestination(instruction, DestinationBinding(1, 11, tag))
        outputs.append(evaluate(_request(bound), destination=bound))
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].element_indices == (4, 5, 6, 7)
    assert outputs[0].active_byte_mask == 0x0FFF


@pytest.mark.parametrize('field,register', ((0, 10), (1, 8), (2, 10), (-1, 8)))
def test_mismatched_architectural_register_field_is_rejected(field, register):
    instruction = DestinationInstruction(4, Fraction(2), 2, 7, 0, 0xFF)
    with pytest.raises(ValueError, match='field|register'):
        expected_destination(BoundDestination(instruction, DestinationBinding(field, register, 0)))


@pytest.mark.parametrize('change', ('owner', 'mask_row', 'vl', 'nf'))
def test_request_cannot_override_a_bound_architectural_identity(change):
    bound = _bound(mask=0b0101)
    request = _request(bound)
    request = replace(request, **{'owner': {'uop_idx': 0}, 'mask_row': {'v0_mask': 0xFFFF},
        'vl': {'vl': 3}, 'nf': {'nf': 1}}[change])
    with pytest.raises(ValueError, match='match'):
        evaluate(request, destination=bound)


@pytest.mark.parametrize('choice', ('ones', 'old'))
def test_both_legal_agnostic_choices_pass_the_independent_oracle(choice):
    bound = _bound(vl=3, vstart=1, mask=0b010, vma=1, vta=1)
    result = evaluate(_request(bound), destination=bound, agnostic_choice=choice)
    oracle = IndependentOracle(4, Fraction(1), 3, 3, 1, 0b010)
    assert not oracle.check_merge_controls(oracle.registers()[1], merge_mask=result.merge_write_mask,
        agnostic_mask=result.agnostic_byte_mask, vma=1, vta=1)


def test_architectural_model_does_not_import_the_adapter_or_qualification_oracle():
    path = Path(__file__).resolve().parents[2] / 'vagqverify/maskgen/architectural.py'
    tree = ast.parse(path.read_text())
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {'dataclasses', 'fractions'}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


def test_independent_wide_fixture_has_fixed_field_and_element_boundaries():
    assert [(f.element, f.field, f.site, f.width) for f in wide_flow(4, 5, 1)] == [
        (0, 4, 0, 4), (1, 0, 4, 12)]
    assert [(f.element, f.field, f.site, f.width) for f in wide_flow(4, 5, 2)] == [
        (1, 3, 0, 8), (2, 0, 8, 8)]


def test_protocol_active_reference_matches_independent_byte_stream_for_every_small_mask():
    checked = 0
    for fields in (5, 6, 7):
        for flow in range(fields):
            fragments = wide_flow(4, fields, flow)
            metadata = flow_metadata(fragments)
            for vl in range(5):
                for start in range(5):
                    for mask in range(16):
                        byte_mask = sum(0xF << (4 * element) for element in range(4) if (mask >> element) & 1)
                        actual = evaluate_protocol(MaskRequest(byte_mask, 2, 2, 0, vl, start, 0, 0, flow, fields - 1))
                        assert all(actual[key] == value for key, value in metadata.items())
                        assert actual['elemActiveMask'] == active_sites(fragments, vl=vl, vstart=start, element_mask=mask)
                        checked += 1
    assert checked == 7200
