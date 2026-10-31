"""Bounded two-key depth-one replay state, with independent counter routing.

Entry key hits retain their shadow owner. New record initialization belongs to
that owner, never an unrelated nominated request way. Other identities and
undefined payload placeholders are left untouched. This bounded helper takes
already-checked public profiles; it is not the autonomous MainBTB reference.
"""
from suites.frontend.bpu.models.configuration import *
from copy import deepcopy
from dataclasses import replace


def expected_depth_target_state(prepared, align, owner, target):
    """One logical retarget, independent of a request's physical nomination."""
    if (len(prepared) != 2 or type(align) is not int or align not in (0, 1)
            or type(owner) is not int or owner not in range(MAIN_WAYS)):
        raise ValueError('depth-one state requires two profiles and a physical owner way')
    if type(target) is not int or not 0 <= target < (1 << 49):
        raise ValueError('depth-one state requires an unsigned 49-bit halfword target')
    active = align * (MAIN_WAYS + 1) + owner
    entry = prepared[1]['entries'][active]
    meta = prepared[1]['meta_entries'][align][owner]
    if not entry.valid or entry.branch_type != 3 or not meta['rawHit'] or meta['counter_value'] != 2:
        raise ValueError('depth-one replay requires an indirect owner hit with counter 2')
    if (entry.position != meta['position'] or meta['attribute']['branchType'] != 3
            or entry.ras_action != meta['attribute']['rasAction']):
        raise ValueError('depth-one owner entry and source metadata must identify the same indirect branch')
    states = deepcopy(prepared)
    states[1]['entries'] = tuple(replace(value, taken=1, target=target) if index == active else value
                                for index, value in enumerate(states[1]['entries']))
    states[1]['meta_entries'][align][owner]['counter_value'] = 2
    return states


def expected_mbtb_depth_one_states(prepared, align, owner, targets, request_ways):
    """Legacy two-offer program; nominations qualify that program, not owners."""
    if len(targets) != 2 or any(type(value) is not int or not 0 <= value < (1 << 49) for value in targets):
        raise ValueError('depth-one state requires two unsigned 49-bit halfword target rewrites')
    request_ways = tuple(request_ways)
    if (type(request_ways) is not tuple or len(request_ways) != 2
            or any(type(way) is not int or way not in range(4) for way in request_ways)
            or len(set(request_ways)) != 2):
        raise ValueError('depth-one replay must nominate two distinct physical request ways')
    return expected_depth_target_state(prepared, align, owner, targets[-1])
