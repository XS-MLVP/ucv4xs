"""Normative RVV v1.0 facts used by the VAGQ ISA audit.

This module intentionally does not import the MaskGen/AddrGen references or
any Chisel-derived MOP table.  It models architectural element classification,
vector-memory addresses, segment fields, ordering constraints, agnostic
destination outcomes, and a minimal precise-trap restart relation.  It is not
a timing model and it does not assume the VAGQ implementation's MOP layout.
"""
from dataclasses import dataclass
from fractions import Fraction


VLEN_BYTES = 16
U64_MASK = (1 << 64) - 1
XLEN_BITS = 64

SEW_BITS_BY_ENCODING = {0: 8, 1: 16, 2: 32, 3: 64}

# Signed vlmul encoding from RVV v1.0, represented as exact fractions.
LMUL_BY_ENCODING = {
    0: Fraction(1),
    1: Fraction(2),
    2: Fraction(4),
    3: Fraction(8),
    5: Fraction(1, 8),
    6: Fraction(1, 4),
    7: Fraction(1, 2),
}

# The signed exponent encoded by vtype.vlmul.  Keeping the exponent separate
# from the Fraction is useful when checking the public VAGQ ``emul`` field.
LMUL_EXP_BY_ENCODING = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    5: -3,
    6: -2,
    7: -1,
}


def lmul(vlmul):
    try:
        return LMUL_BY_ENCODING[vlmul]
    except KeyError as exc:
        raise ValueError(f"reserved vlmul encoding: {vlmul}") from exc


def sew_bits(vsew):
    try:
        return SEW_BITS_BY_ENCODING[vsew]
    except KeyError as exc:
        raise ValueError(f"reserved vsew encoding: {vsew}") from exc


def lmul_exponent(vlmul):
    try:
        return LMUL_EXP_BY_ENCODING[vlmul]
    except KeyError as exc:
        raise ValueError(f"reserved vlmul encoding: {vlmul}") from exc


def vlmax(*, vsew, vlmul, vlen_bytes=VLEN_BYTES):
    """Return architectural VLMAX = LMUL * VLEN / SEW."""
    result = Fraction(vlen_bytes * lmul(vlmul), 1 << vsew)
    if result.denominator != 1:
        raise ValueError(
            f"configuration has no whole architectural element: "
            f"vsew={vsew}, vlmul={vlmul}, VLMAX={result}"
        )
    return result.numerator


def emul_encoding(*, vsew, vlmul, eew):
    """Return the RVV effective-LMUL exponent for an EEW operand.

    RVV defines ``EMUL = (EEW / SEW) * LMUL``.  The VAGQ public field uses the
    same signed three-bit exponent encoding as ``vlmul``.  A result outside
    the supported -3..3 range is not a legal VAGQ operand.
    """
    exponent = lmul_exponent(vlmul) + eew - vsew
    if exponent not in (-3, -2, -1, 0, 1, 2, 3):
        raise ValueError(f"EMUL exponent outside RVV encoding: {exponent}")
    return {
        -3: 5,
        -2: 6,
        -1: 7,
        0: 0,
        1: 1,
        2: 2,
        3: 3,
    }[exponent]


def validate_vector_configuration(*, vsew, vlmul, vl, vstart, vlen_bits=128):
    """Validate the architectural domain used by a VAGQ memory operation."""
    if vlen_bits <= 0 or vlen_bits % 8:
        raise ValueError(f"VLEN must be a positive byte multiple: {vlen_bits}")
    maximum = vlmax(
        vsew=vsew, vlmul=vlmul, vlen_bytes=vlen_bits // 8,
    )
    if vl < 0 or vl > maximum:
        raise ValueError(f"vl={vl} outside [0,VLMAX={maximum}]")
    if vstart < 0:
        raise ValueError(f"negative vstart: {vstart}")
    return maximum


@dataclass(frozen=True, slots=True)
class ElementState:
    index: int
    kind: str

    @property
    def participates_in_memory(self):
        return self.kind == "active"


def classify_elements(*, vl, vstart, vlmax_value, mask):
    """Classify every architectural element in a vector register group.

    RVV treats an operation with ``vstart >= vl`` specially: no body exists
    and no tail elements are updated with agnostic values.  The classifier
    still labels indices at/after vl as tail for reporting, while callers that
    reason about destination writes use ``allowed_destination_values`` below.
    """
    if vl < 0 or vstart < 0 or vlmax_value < 0:
        raise ValueError("vl, vstart, and VLMAX must be non-negative")
    result = []
    for index in range(vlmax_value):
        if index < vstart:
            kind = "prestart"
        elif index < vl and vstart < vl:
            kind = "active" if ((mask >> index) & 1) else "inactive"
        else:
            kind = "tail"
        result.append(ElementState(index, kind))
    return tuple(result)


def active_elements(*, vl, vstart, vlmax_value, mask):
    """Return RVV active element indices for a non-faulting memory operation.

    Elements before ``vstart`` are prestart, elements at/after ``vl`` are
    tail, and masked-off body elements are inactive.  None of these generate
    a memory access.  The mask is indexed by architectural element index; the
    VAGQ byte expansion is deliberately not used here.
    """
    return tuple(
        item.index for item in classify_elements(
            vl=vl, vstart=vstart, vlmax_value=vlmax_value, mask=mask,
        ) if item.participates_in_memory
    )


def _signed_xlen(value, width=64):
    value &= (1 << width) - 1
    return value - (1 << width) if value & (1 << (width - 1)) else value


def index_element(data, *, index, ieew):
    """Read an unsigned indexed offset from one VLEN-wide vector register."""
    width = 1 << ieew
    count = (VLEN_BYTES * 8) // (width * 8)
    if count <= 0:
        raise ValueError(f"invalid index EEW encoding: {ieew}")
    local = index % count
    return (data >> (local * width * 8)) & ((1 << (width * 8)) - 1)


@dataclass(frozen=True, slots=True)
class MemoryAccess:
    """One architectural field access, independent of VAGQ flow packing."""

    element: int
    field: int
    address: int


@dataclass(frozen=True, slots=True)
class FlowFragment:
    """A byte fragment visible in one 16-byte VAGQ memory flow."""

    element: int
    field: int
    flow: int
    byte_offset: int
    width: int
    state: str


def flow_fragments(*, vsew, vlmul, vl, vstart, mask, data_eew, nf=0,
                   uop_idx, vlen_bits=128, active_only=False):
    """Partition the architectural segment memory layout into VAGQ flows.

    The partition is derived from the public 16-byte flow width and the RVV
    segment memory layout: fields of one segment element are contiguous in
    memory.  It does not use ``VagqInfoGen.instTable`` or any generated lookup
    value.  ``uop_idx`` is treated only as a physical flow selector; callers
    still have to verify that the producer's uop sequence covers every needed
    flow exactly once.
    """
    if uop_idx < 0:
        raise ValueError(f"negative uop index: {uop_idx}")
    maximum = validate_vector_configuration(
        vsew=vsew, vlmul=vlmul, vl=vl, vstart=vstart, vlen_bits=vlen_bits,
    )
    states = classify_elements(
        vl=vl, vstart=vstart, vlmax_value=maximum, mask=mask,
    )
    data_bytes = 1 << data_eew
    fields = nf + 1
    segment_bytes = data_bytes * fields
    result = []
    for item in states:
        if active_only and not item.participates_in_memory:
            continue
        for field in range(fields):
            start = item.index * segment_bytes + field * data_bytes
            end = start + data_bytes
            flow = start // VLEN_BYTES
            if flow != uop_idx and end <= uop_idx * VLEN_BYTES:
                continue
            if start >= (uop_idx + 1) * VLEN_BYTES:
                continue
            fragment_start = max(start, uop_idx * VLEN_BYTES)
            fragment_end = min(end, (uop_idx + 1) * VLEN_BYTES)
            result.append(FlowFragment(
                element=item.index,
                field=field,
                flow=uop_idx,
                byte_offset=fragment_start - uop_idx * VLEN_BYTES,
                width=fragment_end - fragment_start,
                state=item.kind,
            ))
    return tuple(result)


def architectural_accesses(*, kind, base, vsew, vlmul, vl, vstart, mask,
                           data_eew, nf=0, ordered=False, stride=0,
                           index_data=0, index_values=None, index_eew=0,
                           vlen_bits=128):
    """Return the active RVV vector-memory accesses for one instruction.

    ``nf`` is the encoded segment field count minus one, so ``nf=0`` means a
    non-segment operation and ``nf=4`` means five fields.  For a segment, the
    element index is shared by all fields.  Unit-stride is included for the
    architectural oracle even though the current VAGQ public path does not
    accept unit-stride instructions.
    """
    if kind not in ("unit", "strided", "indexed"):
        raise ValueError(f"unknown vector-memory kind: {kind}")
    if not 0 <= data_eew <= 3 or not 0 <= index_eew <= 3:
        raise ValueError("EEW encoding outside RVV v1.0 domain")
    if not 0 <= nf <= 7:
        raise ValueError(f"nf outside RVV segment domain: {nf}")
    maximum = validate_vector_configuration(
        vsew=vsew, vlmul=vlmul, vl=vl, vstart=vstart, vlen_bits=vlen_bits,
    )
    states = classify_elements(
        vl=vl, vstart=vstart, vlmax_value=maximum, mask=mask,
    )
    data_bytes = 1 << data_eew
    fields = nf + 1
    accesses = []
    for item in states:
        if not item.participates_in_memory:
            continue
        for field in range(fields):
            if kind == "unit":
                displacement = (item.index * fields + field) * data_bytes
            elif kind == "strided":
                displacement = _signed_xlen(stride) * item.index
                displacement += field * data_bytes
            else:
                if index_values is not None:
                    if item.index >= len(index_values):
                        raise ValueError(
                            f"index vector has no element {item.index}"
                        )
                    index_value = index_values[item.index]
                else:
                    index_value = index_element(
                        index_data, index=item.index, ieew=index_eew,
                    )
                displacement = index_value
                displacement += field * data_bytes
            accesses.append(MemoryAccess(
                element=item.index,
                field=field,
                address=(base + displacement) & U64_MASK,
            ))
    return tuple(accesses)


def access_order_is_legal(accesses, *, ordered, segmented=False):
    """Check the RVV memory-order constraint for an observed access trace.

    Unordered indexed operations accept any order.  Ordered non-segment
    operations require strictly increasing element indices.  Ordered segment
    operations require nondecreasing element groups, while fields inside one
    segment may appear in any order per RVV v1.0.
    """
    if not ordered:
        return True
    elements = [access.element for access in accesses]
    if segmented:
        return all(left <= right for left, right in zip(elements, elements[1:]))
    return all(left < right for left, right in zip(elements, elements[1:]))


def restart_accesses(accesses, *, fault_element):
    """Architectural suffix that must be executed after a precise trap."""
    if fault_element < 0:
        raise ValueError(f"negative fault element: {fault_element}")
    return tuple(access for access in accesses if access.element >= fault_element)


def completed_before_fault(accesses, *, fault_element):
    """Accesses belonging to elements strictly before a reported fault."""
    return tuple(access for access in accesses if access.element < fault_element)


def allowed_destination_values(*, old, computed, state, element_bits,
                               vma, vta, vstart, vl):
    """Return the RVV-allowed values for one destination element.

    Agnostic means the implementation may retain the old value or write all
    ones.  If ``vstart >= vl``, RVV explicitly disallows agnostic tail updates,
    so all non-active elements remain undisturbed.
    """
    all_ones = (1 << element_bits) - 1
    if state == "active":
        return frozenset((computed,))
    if state == "inactive":
        return frozenset((old, all_ones)) if vma else frozenset((old,))
    if state == "tail" and vstart < vl and vta:
        return frozenset((old, all_ones))
    return frozenset((old,))


def destination_value_is_legal(*, value, old, computed, state, element_bits,
                               vma, vta, vstart, vl):
    return value in allowed_destination_values(
        old=old,
        computed=computed,
        state=state,
        element_bits=element_bits,
        vma=vma,
        vta=vta,
        vstart=vstart,
        vl=vl,
    )


def address(*, kind, base, element, stride=0, index_data=0, ieew=0,
            field=0, data_eew=0):
    """RVV vector-memory address equation, reduced modulo XLEN=64.

    ``field`` is the field number within one segment.  A segment field is
    addressed relative to the same element's base; it is not an increment to
    the vector element index.
    """
    field_offset = field * (1 << data_eew)
    if kind == "strided":
        displacement = _signed_xlen(stride) * element
    elif kind == "indexed":
        displacement = index_element(index_data, index=element, ieew=ieew)
    else:
        raise ValueError(f"unknown vector-memory kind: {kind}")
    return (base + displacement + field_offset) & U64_MASK


def ordered_memory_accesses(*, ordered, element_indices):
    """Architectural ordering obligation for indexed memory operations.

    Ordered indexed loads/stores must access elements in increasing element
    order.  Unordered operations impose no such order.  This helper returns
    the required sequence for the simple distinct-element audit, or ``None``
    when no order is imposed.  It is not a timing model.
    """
    sequence = tuple(element_indices)
    return (sequence,) if ordered else None
