"""RVV 1.0 destination-register oracle, independent of any implementation.

Inputs are architectural field/register identities, element width, EMUL,
vl/vstart and one mask bit per element. No uop, MOP, RTL, decoder table,
MaskGen reference or native observations are imported or read here.

Specification anchors: sec-aos, sec-inactive-defs, sec-agnostic and Mapping
of Vector Elements to Vector Register State. Agnostic is an ALLOWED SET,
not a requirement to reproduce any implementation's selected value.
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Register:
    field: int
    number: int
    elements: tuple


@dataclass(frozen=True)
class Instruction:
    eew_bytes: int
    emul: Fraction
    fields: int
    vl: int
    vstart: int
    mask: int
    vlen_bytes: int = 16
    first_register: int = 8

    def __post_init__(self):
        if self.eew_bytes not in (1, 2, 4, 8) or self.vlen_bytes % self.eew_bytes:
            raise ValueError('unsupported whole-element register geometry')
        if self.emul not in tuple(Fraction(2) ** exponent for exponent in range(-3, 4)):
            raise ValueError('EMUL is not a defined power of two')
        if not 1 <= self.fields <= 8 or self.emul * self.fields > 8:
            raise ValueError('reserved segment register group')
        maximum = Fraction(self.vlen_bytes) * self.emul / self.eew_bytes
        if maximum.denominator != 1 or maximum < 1:
            raise ValueError('no whole architectural element')
        if not 0 <= self.vl <= int(maximum) or self.vstart < 0 or self.mask < 0:
            raise ValueError('invalid architectural length/start/mask')
        count = max(1, int(self.emul))
        if self.first_register % count or self.first_register + count * self.fields > 32:
            raise ValueError('unaligned or overflowing architectural register group')

    @property
    def vlmax(self):
        return int(Fraction(self.vlen_bytes) * self.emul / self.eew_bytes)

    @property
    def no_op(self):
        return self.vstart >= self.vl

    def registers(self):
        """Pack each FIELD from element zero; other fields restart at zero."""
        count = max(1, int(self.emul))
        per_register = self.vlen_bytes // self.eew_bytes
        result = []
        for field in range(self.fields):
            # Fractional EMUL still has one register; unused slots are tail.
            element = 0
            for register_number in range(self.first_register + field * count,
                                         self.first_register + (field + 1) * count):
                elements = tuple(range(element, element + per_register))
                result.append(Register(field, register_number, elements))
                element += per_register
        return tuple(result)

    def state(self, element):
        if self.no_op or element < self.vstart:
            return 'undisturbed'
        if element >= self.vl:
            return 'tail'
        return 'active' if (self.mask >> element) & 1 else 'inactive'

    def values(self, register, element):
        """Disjoint old/computed/poison values make clobbers observable."""
        old = tuple(0x10 + (register.field * 7 + element * 3 + byte) % 48
                    for byte in range(self.eew_bytes))
        computed = tuple(0x80 + (register.field * 11 + element * 5 + byte) % 64
                         for byte in range(self.eew_bytes))
        return old, computed

    def allowed(self, register, element, *, vma, vta):
        old, computed = self.values(register, element)
        state = self.state(element)
        if state == 'active':
            return frozenset((computed,))
        if state == 'inactive' and vma or state == 'tail' and vta:
            return frozenset((old, (0xFF,) * self.eew_bytes))
        return frozenset((old,))

    def check_merge_controls(self, register, *, merge_mask, agnostic_mask, vma, vta):
        """Check the architectural effect of applying proposed merge controls.

        Active load results are assumed available before this merge step;
        that assumption does not verify a DUT's data transport. Inactive
        bytes start with poison, so missing preservation cannot go unnoticed.
        On a no-op the initial register is old, never an active result.
        """
        if not 0 <= merge_mask < (1 << self.vlen_bytes) or not 0 <= agnostic_mask < (1 << self.vlen_bytes):
            raise ValueError('control width exceeds one architectural register')
        errors = []
        for slot, element in enumerate(register.elements):
            old, computed = self.values(register, element)
            initial = old if self.no_op else computed if self.state(element) == 'active' else (
                (0x60,) * self.eew_bytes)
            value = []
            for byte, previous in enumerate(initial):
                bit = 1 << (slot * self.eew_bytes + byte)
                value.append((0xFF if agnostic_mask & bit else old[byte])
                             if merge_mask & bit else previous)
            allowed = self.allowed(register, element, vma=vma, vta=vta)
            if tuple(value) not in allowed:
                errors.append(dict(field=register.field, register=register.number,
                    element=element, state=self.state(element), value=value,
                    allowed=[list(item) for item in sorted(allowed)]))
        return errors

    def expanded_mask(self, register):
        """Convert one architectural mask bit per element to a byte input."""
        result = 0
        for slot, element in enumerate(register.elements):
            if (self.mask >> element) & 1:
                for byte in range(self.eew_bytes):
                    result |= 1 << (slot * self.eew_bytes + byte)
        return result
