"""Independent fixture for whole-EMUL=1 wide segment byte streams.

This is deliberately NOT a universal producer adapter. Tests use index EEW
equal to data EEW, so the four-element index bank cannot split a flow in its
middle. A fixture's metadata is checked before any RTL active-mask conclusion.
No generated decoder, MOP adapter, or DUT-derived expected mask is used.
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fragment:
    element: int
    field: int
    site: int
    width: int


def wide_flow(eew_bytes, fields, flow):
    if eew_bytes not in (1, 2, 4, 8) or not 2 <= fields <= 8 or fields * eew_bytes <= 16:
        raise ValueError('fixture requires a wide segment and a supported EEW')
    if not 0 <= flow < fields:
        raise ValueError('flow outside the EMUL=1 register allocation')
    begin, end = flow * 16, (flow + 1) * 16
    width = fields * eew_bytes
    fragments = []
    # Element-major memory stream, derived directly from segment fields.
    for element in range(16 // eew_bytes):
        start = max(begin, element * width)
        stop = min(end, (element + 1) * width)
        if start < stop:
            fragments.append(Fragment(element, (start - element * width) // eew_bytes,
                                      start - begin, stop - start))
    if not fragments:
        raise ValueError('empty physical flow')
    return tuple(fragments)


def flow_metadata(fragments):
    first = fragments[0]
    return dict(elemBase=first.element, startFieldOffset=first.field,
        startByteOffset=first.site, elemValidMask=sum(1 << fragment.site for fragment in fragments))


def active_sites(fragments, *, vl, vstart, element_mask):
    return sum(1 << fragment.site for fragment in fragments
        if vstart <= fragment.element < vl and (element_mask >> fragment.element) & 1)
