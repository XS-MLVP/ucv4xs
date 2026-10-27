"""Port encoding only; not imported by the reference or its expected generator."""
from .types import Beat, Idle, Offer

WIDTHS = dict(reset=1, in_reqValid=1, in_reqCount=4, in_releaseMask=8,
              in_redirect=1, in_bitMapMask=8, in_walkValid=1, in_walkMask=8,
              out_allocValid=1, out_entryIdx=3, out_allocMask=8)


def mask(entries):
    return sum(1 << position for position in entries)


def entries(value):
    return frozenset(position for position in range(8) if value & 1 << position)


def encode(beat):
    return dict(reqValid=int(isinstance(beat.request, Offer)),
                reqCount=beat.request.count if isinstance(beat.request, Offer)
                         else beat.request.count_encoding,
                releaseMask=mask(beat.released), redirect=int(beat.recovery is not None),
                bitMapMask=0 if beat.recovery is None else mask(beat.recovery),
                walkValid=int(beat.walked is not None),
                walkMask=0 if beat.walked is None else mask(beat.walked))


def decode(values):
    return Beat(Offer(values['reqCount']) if values['reqValid'] else Idle(values['reqCount']),
                entries(values['releaseMask']),
                entries(values['bitMapMask']) if values['redirect'] else None,
                entries(values['walkMask']) if values['walkValid'] else None)
