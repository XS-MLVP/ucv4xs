"""Fixed RVV facts; expected answers never import or inspect the RTL."""
import ast
from fractions import Fraction
from pathlib import Path

import pytest

from vagqverify.qualification.rvv_destination import Instruction
from vagqverify.maskgen.reference import MaskRequest, evaluate_protocol


pytestmark = pytest.mark.toffee_functional_coverage(False)


def test_oracle_imports_only_standard_library_and_has_no_external_reads():
    path = Path(__file__).resolve().parents[2] / 'vagqverify/qualification/rvv_destination.py'
    tree = ast.parse(path.read_text())
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {'dataclasses', 'fractions'}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in ('open', 'eval', 'exec', '__import__') for node in ast.walk(tree))


def test_each_segment_field_restarts_at_element_zero_not_at_next_register_index():
    instruction = Instruction(4, Fraction(1), 3, 4, 0, 0xF)
    assert [(reg.field, reg.number, reg.elements) for reg in instruction.registers()] == [
        (0, 8, (0, 1, 2, 3)), (1, 9, (0, 1, 2, 3)), (2, 10, (0, 1, 2, 3)),
    ]
    for register in instruction.registers():
        assert not instruction.check_merge_controls(register, merge_mask=0, agnostic_mask=0, vma=0, vta=0)
        # This is the old bug's EFFECT, rejected without consulting DUT output.
        assert instruction.check_merge_controls(register, merge_mask=0xFFFF, agnostic_mask=0, vma=0, vta=0)


def test_multiple_registers_extend_a_field_then_the_next_field_restarts():
    instruction = Instruction(4, Fraction(2), 2, 7, 1, 0x55)
    assert [(reg.number, reg.elements) for reg in instruction.registers()] == [
        (8, (0, 1, 2, 3)), (9, (4, 5, 6, 7)),
        (10, (0, 1, 2, 3)), (11, (4, 5, 6, 7)),
    ]


def test_fractional_unused_physical_register_space_is_tail_not_more_active_elements():
    instruction = Instruction(2, Fraction(1, 4), 5, 2, 0, 0b11)
    assert instruction.vlmax == 2
    for register in instruction.registers():
        assert [instruction.state(element) for element in register.elements] == ['active'] * 2 + ['tail'] * 6
        assert not instruction.check_merge_controls(register, merge_mask=0xFFF0, agnostic_mask=0, vma=0, vta=0)


def test_agnostic_is_a_set_and_an_implementation_different_from_rtl_can_be_legal():
    instruction = Instruction(1, Fraction(1), 2, 3, 1, 0b010)
    register = instruction.registers()[0]
    # Active element 1 must survive. Others may be old; tail may also be ones.
    assert not instruction.check_merge_controls(register, merge_mask=0xFFFD, agnostic_mask=0,
                                                vma=1, vta=1)
    assert not instruction.check_merge_controls(register, merge_mask=0xFFFD, agnostic_mask=0xFFFC,
                                                vma=1, vta=1)
    # Prestart is never agnostic, even when both policy bits are set.
    assert instruction.check_merge_controls(register, merge_mask=0xFFFD, agnostic_mask=0xFFFF,
                                            vma=1, vta=1)


@pytest.mark.parametrize('vl,vstart', ((0, 0), (2, 2), (2, 3)))
def test_no_op_instructions_must_not_apply_agnostic_tail_updates(vl, vstart):
    instruction = Instruction(1, Fraction(1), 2, vl, vstart, 0xFFFF)
    assert instruction.no_op
    for register in instruction.registers():
        assert not instruction.check_merge_controls(register, merge_mask=0, agnostic_mask=0,
                                                    vma=1, vta=1)
        assert instruction.check_merge_controls(register, merge_mask=0xFFFF, agnostic_mask=0xFFFF,
                                                vma=1, vta=1)


def test_fixed_reference_repair_against_a_hand_derived_architectural_register():
    instruction = Instruction(4, Fraction(1), 3, 4, 0, 0xF)
    for uop, register in enumerate(instruction.registers()):
        controls = evaluate_protocol(MaskRequest(0xFFFF, 2, 2, 0, 4, 0, 0, 0, uop, 2))
        assert not instruction.check_merge_controls(register,
            merge_mask=controls['mergeWriteMask'], agnostic_mask=controls['elemAgnosticMask'], vma=0, vta=0)
