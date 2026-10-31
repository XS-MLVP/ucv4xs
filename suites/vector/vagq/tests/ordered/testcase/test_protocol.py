"""OrderedPermitCtrl scenarios are domain beats; no raw pin writes in cases."""
import pytest

from suites.vector.vagq.ordered.types import Beat, Entry, Redirect, SplitDone

ORDERED_LOAD = 0b110
ORDERED_STORE = 0b111
UNORDERED_LOAD = 0b100
WAIT_A = 1


def blank():
    return [Entry() for _ in range(8)]


def make(*items, split=None, redirect=None):
    values = blank()
    for index, entry in items:
        values[index] = entry
    return Beat(tuple(values), split or SplitDone(), redirect or Redirect())


def load(*, uop=0, rob=10, flag=0, last=False, exception=False, state=3):
    return Entry(True, ORDERED_LOAD, flag, rob, uop, last, exception, state)


@pytest.mark.asyncio
async def test_ordered_permit_lifecycle_and_redirect_contract(ordered_env):
    env = ordered_env
    await env.reset()

    # Entry gates: invalid, unordered load, store, ordered first, then waiting.
    await env.step(Beat())
    await env.step(make((0, Entry(True, UNORDERED_LOAD, uop_idx=3))))
    await env.step(make((0, Entry(True, ORDERED_STORE, uop_idx=3))))
    await env.step(make((0, load(uop=0))))

    # A middle ordered load hands off to the adjacent physical entry.
    await env.step(make((0, load(uop=0)), (1, load(uop=1)), split=SplitDone(True, 0)))
    await env.step(make((0, load(uop=1))))

    # The successor consumes its permit and hands the next one off in one edge.
    await env.step(make((1, load(uop=1)), (2, load(uop=2)), split=SplitDone(True, 1)))
    await env.step(make((2, load(uop=2, last=True)), split=SplitDone(True, 2)))

    # Exception and unmatched-uop completion consume without granting a successor.
    await env.step(make((2, load(uop=0)), (3, load(uop=1)), split=SplitDone(True, 2)))
    await env.step(make((3, load(uop=1, exception=True)), split=SplitDone(True, 3)))
    await env.step(make((4, load(uop=1, last=True)), split=SplitDone(True, 4)))

    # Handoff from entry 7 wraps to entry 0, making a previously waiting uop run.
    await env.step(make((6, load(uop=0)), (7, load(uop=1)), split=SplitDone(True, 6)))
    await env.step(make((7, load(uop=0)), (0, load(uop=1)), split=SplitDone(True, 7)))
    await env.step(make((0, load(uop=1))))

    # A waitA target is allowed to receive the permit before its metadata is ready.
    await env.step(make(
        (0, load(uop=1, rob=20)),
        (1, load(uop=2, rob=20, state=WAIT_A)),
        split=SplitDone(True, 0),
    ))

    # Redirect levels distinguish flushing itself from only younger ROB entries.
    await env.step(make(redirect=Redirect(True, 1, 0, 20)))
    await env.step(make((0, load(uop=0, rob=21)), (1, load(uop=1, rob=21)), split=SplitDone(True, 0)))
    await env.step(make(redirect=Redirect(True, 0, 0, 20)))
    await env.step(make((0, load(uop=0, rob=19)), (1, load(uop=1, rob=19)), split=SplitDone(True, 0)))
    await env.step(make(redirect=Redirect(True, 0, 0, 20)))
    await env.step(make((0, load(uop=0, rob=5)), (1, load(uop=1, rob=5, flag=0)), split=SplitDone(True, 0)))
    await env.step(make(redirect=Redirect(True, 0, 1, 1)))

    # Exercise the physical middle successor slots as well as low/wrap slots.
    await env.reset()
    await env.step(make((3, load(uop=0, rob=30)), (4, load(uop=1, rob=30)), split=SplitDone(True, 3)))
    await env.step(make((4, load(uop=1, rob=30)), (5, load(uop=2, rob=30)), split=SplitDone(True, 4)))
    await env.step(make((5, load(uop=2, rob=30)), (6, load(uop=3, rob=30)), split=SplitDone(True, 5)))

    # Toggle every ROB/flag/uop payload bit on a real permit handoff.  The
    # earlier semantic cases intentionally use small ROB values; this pair
    # makes the native RTL toggle points observe both all-one and all-zero
    # metadata without changing the ordering contract.
    await env.reset()
    await env.step(make(
        (0, load(uop=0, rob=0x1ff, flag=1)),
        (1, load(uop=1, rob=0x1ff, flag=1)),
        split=SplitDone(True, 0),
    ))
    await env.step(make(
        (1, load(uop=1, rob=0, flag=0)),
        (2, load(uop=2, rob=0, flag=0)),
        split=SplitDone(True, 1),
    ))

    # Repeat the handoff over every physical permit slot so the saved permit
    # metadata, not only the first two entries, sees both payload polarities.
    await env.reset()
    for index in range(8):
        target = (index + 1) & 7
        await env.step(make(
            (index, load(uop=0, rob=0x1ff, flag=1)),
            (target, load(uop=1, rob=0x1ff, flag=1)),
            split=SplitDone(True, index),
        ))
        await env.step(make(
            (target, load(uop=1, rob=0, flag=0)),
            split=SplitDone(True, target),
        ))

    env.coverage.group.assert_coverage(100)
    assert env.checker.board.status.failed == 0
