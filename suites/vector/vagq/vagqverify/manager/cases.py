"""Public control programs, independent of pin encoders and observed DUT outputs."""
from itertools import product
import random

from .model import positions
from .types import Beat, Idle, Offer


def all_ring_offers():
    # Public redirect installs each occupancy. The following request observes
    # that state after its precedence-controlled transition, without native writes.
    for bitmap, valid, count in product(range(256), (0, 1), range(16)):
        yield Beat(recovery=positions(bitmap))
        yield Beat(Offer(count) if valid else Idle(count))


def priority_and_wrap():
    return (
        Beat(),
        Beat(Offer(0)),
        Beat(recovery=positions(0x7E)),
        Beat(Offer(2)),  # only free circular window is 7,0
        Beat(Offer(1), released=frozenset({0})),  # full before release
        Beat(Offer(1)),
        Beat(recovery=frozenset()),
        Beat(Offer(2), walked=frozenset({7}), released=frozenset({7})),
        Beat(Offer(1)),
        Beat(Offer(1), recovery=frozenset({4, 5, 6, 7}),
             walked=frozenset({0, 1}), released=frozenset(range(8))),
        Beat(Offer(4)),
        Beat(recovery=frozenset()),
        Beat(Offer(2), released=frozenset({0, 1})),
        Beat(Offer(1)),
        Beat(),
    )


def random_controls(seed, length):
    rng = random.Random(seed)
    for _ in range(length):
        valid, count = rng.randrange(2), rng.randrange(16)
        release, redirect = rng.randrange(256), rng.randrange(2)
        bitmap, walk, walked = rng.randrange(256), rng.randrange(2), rng.randrange(256)
        yield Beat(Offer(count) if valid else Idle(count), released=positions(release),
                   recovery=positions(bitmap) if redirect else None,
                   walked=positions(walked) if walk else None)


# Each independent expected free-position sequence is fixed before the DUT is
# driven. Filling every free position and then observing a blocked allocation
# exposes both missing occupied bits and spurious occupancy after the transition.
EFFECT_CASES = (
    ('wrap_fills_both_ends', 0x7E, Beat(Offer(2)), ()),
    ('release_does_not_bypass', 0xFF,
     Beat(Offer(2), released=frozenset({0, 1})), (0, 1)),
    ('walk_not_allocate_and_overlap_release', 0,
     Beat(Offer(2), walked=frozenset({7}), released=frozenset({7})),
     (0, 1, 2, 3, 4, 5, 6)),
    ('redirect_replaces_all_other_updates', 0x5A,
     Beat(Offer(1), released=frozenset(range(8)), recovery=frozenset({4, 5, 6, 7}),
          walked=frozenset({0, 1})), (0, 1, 2, 3)),
    ('allocation_survives_overlapping_release', 0,
     Beat(Offer(2), released=frozenset({0, 1})), (2, 3, 4, 5, 6, 7)),
)
