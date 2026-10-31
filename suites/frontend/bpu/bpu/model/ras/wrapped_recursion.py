"""One logical deep-call program, not an enumeration of physical storage."""
from suites.frontend.bpu.ras.model.model import CommittedStack, advance

CAPACITY = len(CommittedStack().cells)
CALLS = tuple(0x40010000 + 0x60 * number for number in range(CAPACITY))
PREFIX, INNER = CALLS[:-1], CALLS[-1]
POSITION = 15
INNER_RETURN, PARENT_RETURN = INNER + 16, PREFIX[-1] + 16
SURVIVING_TOP = PREFIX[-2] + 16
PROFILES = (8, 9)
RULES = ('actual-deep-call-sources', 'older-prefix-retired-before-growth',
         'owned-recursive-prefix-restored', 'committed-storage-really-wrapped',
         'declared-repeat-boundary', 'all-recursive-returns-consumed',
         'distinct-parent-return-consumed', 'retained-older-callers-preserved',
         'every-live-operation-retired-once', 'immutable-originals')


def validate(calls):
    if type(calls) is not int or calls not in PROFILES:
        raise ValueError('full recursive group or one call beyond it required')


def return_targets(calls):
    validate(calls)
    return (INNER_RETURN,) * calls + (PARENT_RETURN,)


def sites():
    return tuple((pc, CALLS[number + 1], 2, 2) for number, pc in enumerate(PREFIX)) + (
        (INNER, INNER, 2, 2), (INNER_RETURN, 0x4001F000, 3, 1),
        (PARENT_RETURN, PARENT_RETURN, 2, 0))


def committed(calls, *, returned=False):
    """Reuse the independent semantic stack; no actual group/metadata input."""
    validate(calls)
    state = CommittedStack()
    for address in (*[pc + 16 for pc in PREFIX], *((INNER_RETURN,) * calls)):
        state = advance(state, 2, address=address)
    if returned:
        for _ in return_targets(calls):
            state = advance(state, 1)
    return state
