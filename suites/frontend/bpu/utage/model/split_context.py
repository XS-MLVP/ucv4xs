"""One input-derived high-index / low-tag context, not an address sweep.

For A -> B -> C -> D -> A, A's response index originates at the older
C -> D request, while the tag folds are captured at D -> A. Compute those
histories independently of the DUT and of the integrated index reference.
The complete 532-bit circular history supplies all 33 folded-history ports.
"""
from dataclasses import dataclass

from suites.frontend.bpu.utage.model.addressing import hash_indices, prediction_tag


@dataclass(frozen=True, slots=True)
class SplitContext:
    pc: int
    index_pc: int
    index_history: int
    tag_history: int
    indices: tuple[int, int]
    lower_tag: int


def _contexts(nodes):
    a, b, c, d = nodes
    result = {}
    for name, first_position in (('positive', 6), ('negative', 10)):
        history, before = 0, {}
        for round_ in range(69):
            for source, target, position in ((a, b, first_position), (b, c, 7), (c, d, 7), (d, a, 7)):
                if round_ == 68:
                    before[source] = history
                cfi = (source & ~15) + position
                path = (((cfi & 511) << 4) ^ (target >> 1)) & 32767
                history = ((history << 2) ^ path) & ((1 << 532) - 1)
        index_history = before[c] & ((1 << 532) - 1)
        tag_history = before[d] & ((1 << 532) - 1)
        indices, tag = hash_indices(d, index_history), prediction_tag(a, tag_history, 0)
        if tag >= 256 or d == a:
            raise AssertionError('split input geometry needs independent PCs and a representable tag')
        result[name] = SplitContext(a, d, index_history, tag_history, indices, tag)
    if result['positive'].indices[1] == result['negative'].indices[1]:
        raise AssertionError('final lower readback needs an independent upper miss context')
    return result


def contexts():
    result = _contexts((0x40010006, 0x40010016, 0x40010080, 0x400101e2))
    if any(value.indices[0] != 494 or value.lower_tag != 112 for value in result.values()):
        raise AssertionError('high-row geometry changed')
    return result


def neighbor_context():
    """One low-row neighbor with a different logical PC, not more high rows."""
    value = _contexts((0x40010046, 0x40010056, 0x400100c0, 0x40010222))['positive']
    if value.indices[0] != 46 or value.lower_tag != 116:
        raise AssertionError('independent neighbor geometry changed')
    return value
