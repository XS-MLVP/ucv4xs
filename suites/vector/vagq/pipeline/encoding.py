"""Explicit flat wire encoding for each pipe's distinct payload."""
from .specs import Spec
from .types import Beat


def encode(spec: Spec, beat: Beat):
    values = {
        'io_in_valid': int(beat.in_valid), 'io_out_ready': int(beat.out_ready),
        'io_rightOutFire': int(beat.right_out_fire), 'io_isFlush': int(beat.is_flush),
    }
    for attribute, wire in spec.fields:
        values['io_in_bits_' + wire] = getattr(beat.payload, attribute)
    return values


def output_names(spec: Spec):
    return ('io_in_ready', 'io_out_valid') + tuple(
        'io_out_bits_' + wire for _, wire in spec.fields
    )
