"""Architectural coordinates qualified by the independently expected slot lattice.

Helpers.compact selects only valid input slots; invalid metadata is unconsumed.
Ifu's carry reconstruction overwrites the first carried slot's endOffset with0.
No other valid metadata, including carry cross/FTQ ownership, is exempted.
"""
from toffee import Scoreboard

from suites.frontend.ifu.model.boundary import BoundaryInput, BoundaryOutput, predict


def check_boundary(request, observed, expected=None):
    if not isinstance(request, BoundaryInput) or not isinstance(observed, BoundaryOutput):
        raise TypeError('InstrBoundary requires a complete semantic request/snapshot')
    oracle = predict(request)
    if expected is not None and not isinstance(expected, BoundaryOutput):
        raise TypeError('InstrBoundary expected value must be a BoundaryOutput')
    wanted = oracle if expected is None else expected
    selected = tuple(slot for slot, valid in enumerate(oracle.valid) if valid)
    expected_fields, actual_fields = {}, {}
    for field in ('valid', 'instr_end_mask', 'first_end_is_half_rvi', 'total_end_is_half_rvi'):
        expected_fields[field] = getattr(wanted, field)
        actual_fields[field] = getattr(observed, field)
    for field in ('is_rvc', 'is_cross_block', 'start_offset', 'end_offset', 'block_sel', 'index'):
        slots = tuple(slot for slot in selected
                      if not (field == 'end_offset' and slot == 0 and request.first_instr_is_half_rvi))
        expected_fields[field] = tuple(getattr(wanted, field)[slot] for slot in slots)
        actual_fields[field] = tuple(getattr(observed, field)[slot] for slot in slots)
    expected_fields['pruned_cross'] = 0
    actual_fields['pruned_cross'] = observed.is_cross_block[-1]
    Scoreboard('ifu.instr_boundary').check(expected=expected_fields, actual=actual_fields)
