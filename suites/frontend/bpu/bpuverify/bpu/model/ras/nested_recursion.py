"""An expanded call-stack oracle, not a replica of compressed RTL groups."""
OUTER, INNER = 0x40014000, 0x40018000
OUTER_RETURN, INNER_RETURN = OUTER + 16, INNER + 16
POSITION = 15
PROFILES = (8, 9)
RULES = ('distinct-outer-and-recursive-sources', 'owned-prefix-restored',
         'all-live-calls-retired', 'every-inner-return-consumed',
         'distinct-outer-return-consumed', 'every-return-retired-once',
         'complete-committed-state-restored', 'immutable-originals')


def expanded_returns(calls):
    if type(calls) is not int or calls not in PROFILES:
        raise ValueError('declared single-group or split-group recursive lifetime required')
    # The same logical address appears once per CALL, irrespective of the
    # implementation's compression count, slot or speculative queue position.
    frames = [OUTER_RETURN, *([INNER_RETURN] * calls)]
    return tuple(reversed(frames))


def sites():
    return ((OUTER, INNER, 2, 2), (INNER, INNER, 2, 2),
            (INNER_RETURN, 0x4001F000, 3, 1), (OUTER_RETURN, OUTER_RETURN, 2, 0))
