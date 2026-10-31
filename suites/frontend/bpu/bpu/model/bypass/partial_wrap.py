"""Partial-wrap preparation predicates over reset-derived state, not DUT data."""
from suites.frontend.bpu.bpu.model.phr.model import fold, folds


def retained_fallback(reference, index):
    hits, preferred, slot = reference.select(index)
    if not hits or preferred or not reference.cells[slot]['payload_valid']:
        return None
    return dict(index=index, slot=slot, hits=hits, mask=reference.mask,
                enq=reference.enq, deq=reference.deq)


def filled_with(reference, index, expected):
    return all(cell['valid'] and cell['index'] == index and cell['payload_valid']
               and all(cell[name] == value for name, value in expected.items())
               for cell in reference.cells)


def qualifies_return_request(token, hash_inputs, *, pc, history, after_tick):
    """A fresh normal request, including tag context; no response-based filter.

    An override can retain a2's index while substituting another payload/tag
    snapshot. An index match alone therefore does not qualify a normal read.
    """
    tag_folds = folds(history)
    return bool(token is not None and token['source_tick'] is not None
        and token['source_tick'] > after_tick and token['pc'] == pc
        and token['folds'] == (fold(history, 6, 6), fold(history, 12, 9))
        and hash_inputs['new_pc'] == pc
        and hash_inputs['s1_folds'] == tuple(tag_folds[i] for i in (1, 2, 7, 8))
        and not any(hash_inputs[name] for name in ('redirect_valid', 's2_override', 's3_override')))
