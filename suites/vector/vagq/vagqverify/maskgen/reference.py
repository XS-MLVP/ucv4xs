"""MaskGen allocation adapter plus an explicitly bound architectural API.

Rename reserves whole physical windows even for fractional data EMUL. Thus
elemValidMask describes allocated bookkeeping slots, while elemActiveMask
describes slots allowed to request memory under vl/vstart/v0. An unused slot
may require an empty marker; it is not an extra architectural element.

This implementation-specific layout uses arithmetic, not generated decoder
logic or DUT samples. Architectural VLMAX/addresses are checked separately by
vagq.isa_reference, which must not import this module.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import ceil

FLOW_BYTES = 16
UOP_MAX = 8
ALL_BYTES = (1 << FLOW_BYTES) - 1
LMUL_VALUES = (
    Fraction(1), Fraction(2), Fraction(4), Fraction(8),
    Fraction(0), Fraction(1, 8), Fraction(1, 4), Fraction(1, 2),
)


def _low_mask(width):
    if width <= 0:
        return 0
    return ALL_BYTES if width >= FLOW_BYTES else (1 << width) - 1


def _ceil_fraction(value):
    return ceil(value.numerator / value.denominator)


@dataclass(frozen=True, slots=True)
class MaskRequest:
    v0_mask: int
    deew: int
    ieew: int
    emul: int
    vl: int
    vstart: int
    vma: int
    vta: int
    uop_idx: int
    nf: int

    def __post_init__(self):
        limits = {
            'v0_mask': (self.v0_mask, 1 << FLOW_BYTES),
            'deew': (self.deew, 4), 'ieew': (self.ieew, 4),
            'emul': (self.emul, 8), 'vl': (self.vl, 1 << 8),
            'vstart': (self.vstart, 1 << 7), 'vma': (self.vma, 2),
            'vta': (self.vta, 2), 'uop_idx': (self.uop_idx, UOP_MAX),
            'nf': (self.nf, 8),
        }
        for name, (value, upper) in limits.items():
            if not isinstance(value, int) or not 0 <= value < upper:
                raise ValueError(f'{name} outside MaskGen input encoding: {value!r}')

    @property
    def lmul(self):
        return LMUL_VALUES[self.emul]

    @property
    def legal(self):
        if self.lmul <= 0:
            return False
        index_emul = self.lmul * (1 << self.ieew) / (1 << self.deew)
        data_emul = self.lmul * (self.nf + 1)
        data_elements = Fraction(FLOW_BYTES) * self.lmul / (1 << self.deew)
        return (
            Fraction(1, 8) <= index_emul <= 8
            and data_emul <= UOP_MAX
            and data_elements >= 1
            and data_elements.denominator == 1
        )


@dataclass(frozen=True, slots=True)
class Mop:
    index: int
    field: int
    byte: int
    valid_bit: int
    full_mask: int
    mask_index: int


@dataclass(frozen=True, slots=True)
class MopInfo:
    skip_merge: bool
    first: int
    last: int
    first_field: int
    first_byte: int
    valid_mask: int
    full_mask: int
    mask_index: tuple[int, ...]
    destination_window: int  # element window within a field, NOT destination register offset


def _uop(mops, *, destination_window=0, skip_merge=False):
    if not mops:
        return None
    return dict(
        mops=tuple(mops),
        destination_window=destination_window,
        skip_merge=skip_merge,
    )


def _base_uops(request):
    """Build allocated protocol slots for one representable configuration."""
    field_width = 1 << request.deew
    data_width = (request.nf + 1) * field_width
    index_width = 1 << request.ieew
    indices_per_flow = FLOW_BYTES // index_width
    # This is the Rename/MaskGen allocation contract, NOT architectural VLMAX.
    # For mf8/e8 it reserves 16 slots although only 2 elements can be active.
    physical_windows = _ceil_fraction(request.lmul)
    num_elements = FLOW_BYTES * physical_windows // field_width
    index_emul = Fraction(num_elements * index_width, FLOW_BYTES)
    data_emul = physical_windows * (request.nf + 1)
    special = request.nf == 6 and request.deew == 0 and request.ieew == 2
    ones = ALL_BYTES

    if special:
        data_width = 1 << request.ieew

    if request.nf == 6 and request.deew == 0 and request.ieew == 2:
        uops = []
        index_uops = min(_ceil_fraction(index_emul), UOP_MAX)
        for mul_idx in range(index_uops):
            mops = []
            for within in range(indices_per_flow):
                index = mul_idx * indices_per_flow + within
                if index >= num_elements:
                    continue
                byte = within * index_width
                mops.append(Mop(
                    index=index,
                    field=0,
                    byte=byte,
                    valid_bit=(1 << byte) & ones,
                    full_mask=(((1 << index_width) - 1) << byte) & ones,
                    mask_index=(index * field_width) % FLOW_BYTES,
                ))
            uop = _uop(mops)
            if uop is not None:
                uops.append(uop)
        for _ in range(max(0, _ceil_fraction(data_emul) - index_uops)):
            uops.append(_uop((Mop(0, 0, 0, 0, 0, 0),)))
        return uops[:UOP_MAX]

    # A VLEN flow can hold several data elements, but the uop grouping changes
    # whenever one data element is wider than one index element.  This is the
    # layout distinction used by the vector memory operation table; it is not
    # the later MaskGen ``dataWiderThan128`` check.
    if data_width > index_width:
        uops = []
        emul_max = min(_ceil_fraction(data_emul), UOP_MAX)
        sites = [i * data_width for i in range(FLOW_BYTES * emul_max)]
        split_sites = {
            i * (FLOW_BYTES >> request.ieew) * data_width
            for i in range(1, UOP_MAX)
        }
        for mul_idx in range(emul_max):
            interval = set(range(mul_idx * FLOW_BYTES + 1, (mul_idx + 1) * FLOW_BYTES))
            middle = [site for site in sites if site in interval]
            starts = split_sites.intersection(middle)
            raw_sites = [mul_idx * FLOW_BYTES] + middle
            groups = []
            for site in raw_sites:
                if not groups or site in starts:
                    groups.append([site])
                else:
                    groups[-1].append(site)
            for raw_group in groups:
                raw_fields = [site % data_width for site in raw_group]
                if data_width <= FLOW_BYTES and raw_fields[0] != 0:
                    raw_group = raw_group[1:]
                    raw_fields = raw_fields[1:]
                mops = []
                for site, field_byte in zip(raw_group, raw_fields):
                    byte = site % FLOW_BYTES
                    index = site // data_width
                    mops.append(Mop(
                        index=index,
                        field=field_byte >> request.deew,
                        byte=byte,
                        valid_bit=(1 << byte) & ones,
                        full_mask=(((1 << data_width) - 1) << byte) & ones,
                        mask_index=(index * field_width) % FLOW_BYTES,
                    ))
                uop = _uop(mops)
                if uop is not None:
                    uops.append(uop)
        return uops[:UOP_MAX]

    uops = []
    emul_max = min(max(1, _ceil_fraction(index_emul)), UOP_MAX)
    for mul_idx in range(emul_max):
        mops = []
        data_width_per_uop = data_width * indices_per_flow
        uops_per_flow = FLOW_BYTES // data_width_per_uop
        for within in range(indices_per_flow):
            index = mul_idx * indices_per_flow + within
            if index >= num_elements:
                continue
            byte = within * data_width
            if request.nf == 0 and data_width < index_width:
                byte += data_width_per_uop * (mul_idx % uops_per_flow)
            mops.append(Mop(
                index=index,
                field=0,
                byte=byte,
                valid_bit=(1 << byte) & ones,
                full_mask=(((1 << data_width) - 1) << byte) & ones,
                mask_index=(index * field_width) % FLOW_BYTES,
            ))
        uop = _uop(mops)
        if uop is not None:
            uops.append(uop)
    return uops[:UOP_MAX]


def allocated_uops(request):
    """Public producer-layout adapter, not an architectural access oracle.

    A VAGQ uop is not necessarily one packed data flow: index-register
    boundaries may split it further, and fractional EMUL reserves whole
    physical windows.  Consumers can use these immutable MOP descriptions to
    supply the correct source register per uop without consulting DUT outputs.
    """
    if not request.legal:
        raise ValueError('unsupported VAGQ producer-layout encoding')
    return tuple(tuple(uop['mops']) for uop in _base_uops(request))


def mop_info(request):
    if not request.legal:
        return MopInfo(False, 0, 0, 0, 0, 0, 0, (0,) * FLOW_BYTES, 0)
    uops = _base_uops(request)
    if request.uop_idx >= len(uops):
        return MopInfo(False, 0, 0, 0, 0, 0, 0, (0,) * FLOW_BYTES, 0)
    uop_count = len(uops)
    # A fractional data EMUL still occupies one physical VAGQ uop window;
    # it does not create a fractional number of uops or destination windows.
    lmul_slots = max(1, _ceil_fraction(request.lmul))
    uop_per_lmul = max(1, uop_count // lmul_slots)
    uop_offset = request.uop_idx % uop_per_lmul
    lmul_offset = request.uop_idx // uop_per_lmul
    dest_rw = uop_offset <= request.nf or request.nf == 0
    skip_merge = not dest_rw
    # All fields at the same LMUL position contain the same element window.
    # Field-major register numbering (field * LMUL + window) selects a physical
    # destination; it must NOT move vl/vstart to another window of elements.
    # Even skip-merge uops retain their element-window metadata.
    destination_window = lmul_offset
    uop = uops[request.uop_idx]
    mops = uop['mops']
    if not mops:
        return MopInfo(skip_merge, 0, 0, 0, 0, 0, 0, (0,) * FLOW_BYTES, destination_window)
    valid_mask = 0
    full_mask = 0
    mask_index = [0] * FLOW_BYTES
    for mop in mops:
        valid_mask |= mop.valid_bit
        full_mask |= mop.full_mask
        for byte in range(FLOW_BYTES):
            if mop.full_mask & (1 << byte):
                mask_index[byte] = mop.mask_index
    return MopInfo(
        skip_merge=skip_merge,
        first=mops[0].index,
        last=mops[-1].index,
        first_field=mops[0].field,
        first_byte=mops[0].byte,
        valid_mask=valid_mask,
        full_mask=full_mask,
        mask_index=tuple(mask_index),
        destination_window=destination_window,
    )


def _range_mask(point, start, end, start_byte, data_width, *, wider, last_width):
    if point > end:
        return ALL_BYTES
    if point <= start:
        return 0
    covered = last_width if wider else (point - start) * data_width
    return _low_mask(start_byte + covered) & ~_low_mask(start_byte) & ALL_BYTES


def _segment_range(point, start_field, field_width, *, start, end):
    if point >= end:
        return ALL_BYTES
    if point <= start:
        return 0
    return _low_mask((point - start) * field_width)


def evaluate_protocol(request):
    """Raw component contract ONLY; not an architectural no-op/write oracle.

    This intentionally retains the component's admitted-input policy, including
    forced no-op inputs. Use evaluate(..., destination=...) for ISA expectations.
    """
    info = mop_info(request)
    special = request.nf == 6 and request.deew == 0 and request.ieew == 2
    data_width = (1 << request.ieew) if special else (request.nf + 1) * (1 << request.deew)
    wider = data_width > FLOW_BYTES
    last_width = ((request.nf + 1) - info.first_field) << request.deew
    prestart = _range_mask(
        request.vstart, info.first, info.last, info.first_byte, data_width,
        wider=wider, last_width=last_width,
    )
    before_vl = _range_mask(
        request.vl, info.first, info.last, info.first_byte, data_width,
        wider=wider, last_width=last_width,
    )
    v0_for_elements = sum(
        ((request.v0_mask >> source) & 1) << byte
        for byte, source in enumerate(info.mask_index)
    )
    body = before_vl & ~prestart & info.full_mask & ALL_BYTES
    tail = ~prestart & ~before_vl & info.full_mask & ALL_BYTES
    active = body & v0_for_elements
    inactive = body & ~v0_for_elements & ALL_BYTES
    inactive_agnostic = inactive if request.vma else 0
    tail_agnostic = tail if request.vta else 0
    elem_active = active & info.valid_mask
    non_segment_agnostic = inactive_agnostic | tail_agnostic

    fields_per_flow = FLOW_BYTES >> request.deew
    segment_start = info.destination_window * fields_per_flow
    segment_end = (info.destination_window + 1) * fields_per_flow
    field_width = 1 << request.deew
    segment_prestart = _segment_range(
        request.vstart, segment_start, field_width,
        start=segment_start, end=segment_end,
    )
    segment_before_vl = _segment_range(
        request.vl, segment_start, field_width,
        start=segment_start, end=segment_end,
    )
    segment_body = ~segment_prestart & segment_before_vl & ALL_BYTES
    segment_tail = ~segment_prestart & ~segment_before_vl & ALL_BYTES
    segment_active = segment_body & request.v0_mask
    segment_inactive = segment_body & ~request.v0_mask & ALL_BYTES
    segment_agnostic = (
        (segment_inactive if request.vma else 0)
        | (segment_tail if request.vta else 0)
    )
    is_segment = request.nf != 0
    merge_write = (~(segment_body & request.v0_mask) if is_segment else ~active) & ALL_BYTES
    agnostic = segment_agnostic if is_segment else non_segment_agnostic
    return {
        'elemValidMask': info.valid_mask,
        'elemActiveMask': elem_active,
        'elemAgnosticMask': agnostic,
        'mergeWriteMask': merge_write,
        'elemBase': info.first,
        'startFieldOffset': info.first_field,
        'startByteOffset': info.first_byte,
        'skipMerge': int(info.skip_merge),
    }


def evaluate(request, *, destination=None, agnostic_choice='ones'):
    """ISA destination expectation, fail-closed without an explicit identity.

    No field/window is inferred from uop_idx or this module's allocation table.
    A physical pdest is not accepted in place of an architectural register.
    """
    from .architectural import BoundDestination, expected_destination

    if not isinstance(destination, BoundDestination):
        raise ValueError('architectural evaluation requires an explicit BoundDestination; use evaluate_protocol for component outputs')
    instruction, binding = destination.instruction, destination.binding
    expected = expected_destination(destination, agnostic_choice=agnostic_choice)
    actual_geometry = (1 << request.deew, request.lmul, request.nf + 1,
                       request.vl, request.vstart, request.vma, request.vta)
    bound_geometry = (instruction.eew_bytes, instruction.emul, instruction.fields,
                      instruction.vl, instruction.vstart, instruction.vma, instruction.vta)
    if actual_geometry != bound_geometry or request.uop_idx != binding.uop_idx:
        raise ValueError('request does not match the independently bound instruction/owner')
    if request.v0_mask != expected.expanded_element_mask:
        raise ValueError('byte mask row does not match the bound architectural register')
    return expected
