"""Directed legal cases for retained VLQ ROB/tag and reuse toggle gaps.

The pinned 120-entry/160-entry configuration permits these values.  The test
does not poke internal pointers: it reaches the same physical LQ slots through
three complete allocate/complete/reuse lifecycles, while the independent VLQ
ledger checks every public release and recovery result.
"""

from suites.memblock.lsq.vlq.types import Redirect, RobPtr


async def fill_and_drain(env, robs):
    flows = (15,) * 8
    change = await env.cycle(dispatch=env.build_dispatch(flows, robs=robs))
    assert tuple(item.position for item in change.allocated) == tuple(
        range(change.old_tail, change.old_tail + 120)
    )
    await env.idle(2)
    released = await env.complete_and_drain(newest_first=True)
    assert released == tuple(range(change.old_tail, change.old_tail + 120))


async def test_rob_high_bit_former_latter_and_reused_lq_slots(vlq):
    env = vlq

    # First lifetime writes every physical LQ slot with the low ROB value
    # range and former entries.  This establishes the old ownership through
    # the public dispatch/WB/release protocol, not through a DUT register.
    low_former = tuple(RobPtr.encode(i, former=True) for i in range(8))
    await fill_and_drain(env, low_former)

    # Second lifetime reuses all 120 LQ positions with ROB value bit 6 set
    # and latter entries.  It exercises legal high ROB values and the 1->0
    # former transition in each stored slot.
    high_latter = tuple(RobPtr.encode(64 + i, former=False) for i in range(8))
    await fill_and_drain(env, high_latter)

    # Third lifetime returns to a low bit-6 value while crossing the ROB
    # timeline.  The former transition and both toggle directions now occur
    # on the same physical slots, with real completion required afterwards.
    wrapped_former = tuple(RobPtr.encode(128 + i, former=True) for i in range(8))
    await fill_and_drain(env, wrapped_former)

    # Same-cycle dispatch+redirect is a legal producer race in this DUT.  Use
    # a mixed former/latter batch so the cancellation predicates for all
    # dispatch lanes observe their actual condition combinations.  The model
    # checks the delayed recovery tail and prevents a canceled allocation from
    # being counted as completed.
    race_robs = tuple(RobPtr.encode(136 + i // 2, former=not bool(i % 2)) for i in range(8))
    await env.cycle(
        dispatch=env.build_dispatch((1,) * 8, robs=race_robs),
        redirect=Redirect(True, RobPtr.encode(137, former=True), False),
    )
    await env.settle_recovery()
    # flushAfter retains the cutoff ROB slot and older entries.  Complete
    # those survivors through the public WB/release protocol; only the
    # younger same-cycle dispatches are canceled.
    assert tuple(item.position for item in env.model.entries.values()) == (360, 361, 362)
    assert await env.complete_and_drain() == (360, 361, 362)
    assert not env.model.entries
    assert env.observed.empty
