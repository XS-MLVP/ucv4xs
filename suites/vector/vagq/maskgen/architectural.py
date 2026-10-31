"""Architectural destination reference, NOT an implementation-layout model.

Only RVV instruction parameters and an explicit architectural register identity
are accepted. No uop-count formula, MOP table, RTL, native sample, protocol
reference, or qualification-oracle helper is used to derive expected values.
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class DestinationInstruction:
    eew_bytes: int
    emul: Fraction
    fields: int
    vl: int
    vstart: int
    mask: int
    vma: int = 0
    vta: int = 0
    first_register: int = 8
    vlen_bytes: int = 16

    def __post_init__(self):
        object.__setattr__(self, 'emul', Fraction(self.emul))
        if self.eew_bytes not in (1, 2, 4, 8) or self.vlen_bytes != 16:
            raise ValueError('this reference supports VLEN=128 and EEW=8/16/32/64')
        if self.emul not in (Fraction(1, 8), Fraction(1, 4), Fraction(1, 2),
                             Fraction(1), Fraction(2), Fraction(4), Fraction(8)):
            raise ValueError('reserved EMUL')
        if not 1 <= self.fields <= 8 or self.emul * self.fields > 8:
            raise ValueError('reserved segment register group')
        maximum = self.emul * self.vlen_bytes / self.eew_bytes
        if maximum < 1 or maximum.denominator != 1:
            raise ValueError('no whole architectural element')
        if not 0 <= self.vl <= int(maximum) or not 0 <= self.vstart < 128 or self.mask < 0:
            raise ValueError('invalid vl/vstart/element mask')
        if self.vma not in (0, 1) or self.vta not in (0, 1):
            raise ValueError('invalid mask/tail policy')
        count = self.registers_per_field
        if self.first_register < 0 or self.first_register % count or self.first_register + self.fields * count > 32:
            raise ValueError('unaligned or overflowing architectural register group')

    @property
    def registers_per_field(self):
        return 1 if self.emul < 1 else int(self.emul)


@dataclass(frozen=True, slots=True)
class DestinationBinding:
    """Identity supplied by the stimulus/producer, never inferred by the model.

    register_number is an ARCHITECTURAL register, not a physical pdest. The
    uop tag is checked for ownership only; it has no role in expected policy.
    """
    field: int
    register_number: int
    uop_idx: int


@dataclass(frozen=True, slots=True)
class BoundDestination:
    instruction: DestinationInstruction
    binding: DestinationBinding


@dataclass(frozen=True, slots=True)
class DestinationExpectation:
    field: int
    register_number: int
    element_indices: tuple
    active_byte_mask: int
    merge_write_mask: int
    agnostic_byte_mask: int
    expanded_element_mask: int
    instruction_executes: bool
    destination_commit_allowed: bool
    memory_elements: tuple


def expected_destination(bound: BoundDestination, *, agnostic_choice='ones'):
    """Return a legal register policy; 'old' is also legal when agnostic.

    The no-op rule is implemented HERE: no active memory elements and no
    destination commit are permitted, irrespective of producer suppression.
    """
    if not isinstance(bound, BoundDestination):
        raise TypeError('an explicit BoundDestination is required')
    instruction, binding = bound.instruction, bound.binding
    if agnostic_choice not in ('ones', 'old'):
        raise ValueError('agnostic choice must retain old data or write all ones')
    if not 0 <= binding.field < instruction.fields or not 0 <= binding.uop_idx < 8:
        raise ValueError('invalid field or uop ownership tag')
    first = instruction.first_register + binding.field * instruction.registers_per_field
    if not first <= binding.register_number < first + instruction.registers_per_field:
        raise ValueError('register does not belong to the specified architectural field')
    per_register = instruction.vlen_bytes // instruction.eew_bytes
    start = (binding.register_number - first) * per_register
    elements = tuple(range(start, start + per_register))
    executes = instruction.vstart < instruction.vl
    active = agnostic = expanded = 0
    memory = []
    for slot, element in enumerate(elements):
        byte_bits = sum(1 << (slot * instruction.eew_bytes + byte)
                        for byte in range(instruction.eew_bytes))
        selected = bool((instruction.mask >> element) & 1)
        if selected:
            expanded |= byte_bits
        if not executes or element < instruction.vstart:
            continue
        if element < instruction.vl:
            if selected:
                active |= byte_bits
                memory.append(element)
            elif instruction.vma and agnostic_choice == 'ones':
                agnostic |= byte_bits
        elif instruction.vta and agnostic_choice == 'ones':
            agnostic |= byte_bits
    return DestinationExpectation(binding.field, binding.register_number, elements,
        active, ((1 << instruction.vlen_bytes) - 1) ^ active, agnostic, expanded,
        executes, executes, tuple(memory))
