"""Depth-case public projection; valid and filtered-hit sources stay strict."""
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext, Scoreboard, ScoreboardMode


def defined_depth_profile(profile):
    entries, metadata = profile['entries'], profile['meta_entries']
    if len(entries) != 4 or len(metadata) != 2 or any(len(row) != 2 for row in metadata):
        raise ValueError('depth comparison requires two alignments and two ways')
    visible = tuple(asdict(entry) if entry.valid else dict(valid=entry.valid) for entry in entries)
    sources = tuple(tuple(dict(rawHit=source['rawHit'], counter_value=source['counter_value'],
        position=source['position'], attribute=deepcopy(source['attribute']))
        if source['rawHit'] else dict(rawHit=source['rawHit']) for source in row) for row in metadata)
    return dict(entries=visible, meta_entries=sources)


def defined_depth_check(wanted):
    # Freeze now, not when the DUT response arrives. A later mutation of the
    # caller's profile must not redefine what the old transaction expected.
    original = deepcopy(wanted)
    expected = defined_depth_profile(original)
    board = Scoreboard('mbtb.depth-defined-consumer')

    def check(prediction):
        actual = defined_depth_profile(dict(entries=prediction.entries, meta_entries=prediction.meta_entries))
        board.check(expected=expected, actual=actual,
            context=CheckContext(board.name, ScoreboardMode.DIRECT,
                request=dict(expected_profile=original,
                    scope='all valid predictions and every raw-hit source, including filtered hits')))

    return check
