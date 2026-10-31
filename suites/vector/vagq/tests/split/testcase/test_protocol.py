"""SplitCtrl real-DUT scenarios use semantic entries and consumer readiness."""
from suites.vector.vagq.split.types import Beat, Entry, Redirect


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def entry(index, *, active=0x07, valid=0xffff, uop=0, sent=0, ack=0,
          exception=False, fault=0, rob=10, nf=0, deew=0, ieew=0,
          start_field=0, start_byte=0, base=0x1000, elem_base=0,
          rob_flag=0, lq_flag=0, lq=0, sq_first=0, sq_second=0, sq=0,
          op2=4, ftq_flag=0, ftq=None, ftq_off=None):
    if ftq is None:
        ftq = index
    if ftq_off is None:
        ftq_off = index
    return Entry(
        valid=True, uop_type=uop, rob_flag=rob_flag, rob_value=rob,
        base_addr=base, op2_data=op2, deew=deew, ieew=ieew, elem_base=elem_base,
        start_field=start_field, start_byte=start_byte,
        elem_valid=valid, elem_active=active, nf=nf,
        req_sent=sent, req_ack=ack, exception=exception,
        fault_elem=fault, state=3, ftq_flag=ftq_flag, ftq_value=ftq,
        ftq_offset=ftq_off,
        lq_flag=lq_flag, lq_value=lq, sq_first_flag=sq_first,
        sq_second_flag=sq_second, sq_value=sq, pdest=index,
    )


def beat(entries=(), *, redirect=Redirect(), lsu_ready=(False, False, False),
         empty_ready=(False, False)):
    values = [Entry() for _ in range(8)]
    for index, value in entries:
        values[index] = value
    return Beat(tuple(values), redirect, matrix(), lsu_ready, empty_ready)


async def test_split_active_empty_staging_backpressure_and_flush(split_env):
    env = split_env
    await env.reset()

    # A normal load partitions three active elements; the same entry also has
    # inactive bytes, so active and empty stages can accept independently.
    await env.step(beat(((0, entry(0, active=0x07, valid=0x0f)),)))
    await env.step(beat(lsu_ready=(False, False, False), empty_ready=(False, False)))
    await env.step(beat(lsu_ready=(True, True, True), empty_ready=(True, True)))

    # Hold a store request while the consumer is blocked, then fire it.
    await env.step(beat(((1, entry(1, active=0x01, valid=0x01, uop=1)),)))
    await env.step(beat(lsu_ready=(False, False, False)))
    await env.step(beat(lsu_ready=(True, True, True)))

    # Ordered load emits one active lane, while an outstanding active bit blocks
    # new active work but leaves empty work eligible.
    await env.step(beat(((2, entry(2, active=0x03, valid=0x0f, uop=6, sent=0x01)),)))
    await env.step(beat(empty_ready=(True, True)))

    # Fault cancellation emits exception feedback for the later element.
    await env.step(beat(((3, entry(3, active=0x03, valid=0x03, exception=True, fault=0)),)))
    await env.step(beat())

    # A staged request is suppressed and cleared by a matching redirect.
    await env.step(beat(((4, entry(4, active=0x01, valid=0x01, rob=40)),)))
    await env.step(beat(redirect=Redirect(True, 1, 0, 40)))

    # Cover the ordered single-lane path and the wide/last-MOP element shapes.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x03, valid=0x03, uop=6)),)))
    await env.step(beat(lsu_ready=(True, True, True)))
    await env.reset()
    await env.step(beat(((1, entry(1, active=0x01, valid=0x01, nf=2, deew=3)),)))
    await env.step(beat(lsu_ready=(True, True, True)))
    await env.reset()
    # Real e64/3-field continuation: field 2 at flow byte 0, followed by
    # an inactive element at byte 8. The former (site 0 < startByte 1)
    # fixture was internally contradictory, not valid producer metadata.
    await env.step(beat(((2, entry(2, active=0x01, valid=0x101, nf=2, deew=3,
                                  ieew=3, start_field=2, start_byte=0)),)))
    await env.step(beat(lsu_ready=(True, True, True)))

    # Leave both stages occupied, then flush the matching ROB before either
    # consumer fires.
    await env.reset()
    await env.step(beat(((3, entry(3, active=0x01, valid=0x03, rob=44)),)))
    await env.step(beat(redirect=Redirect(True, 1, 0, 44)))

    # Make every physical entry a live candidate once.  The externally
    # supplied older matrix still selects entry 0, but the other candidates
    # exercise the generated per-entry pending/selection network.
    await env.reset()
    await env.step(beat(tuple(
        (index, entry(index, active=0x01, valid=0x01, rob=100 + index))
        for index in range(8)
    )))
    await env.step(beat(lsu_ready=(True, True, True), empty_ready=(True, True)))

    # Drive each data-size encoding and a nonzero site.  The latter is needed
    # for the wide-data address/index path; all payload fields remain checked
    # against the independent AddrGen/element reference.
    for index, (deew, nf, active_mask) in enumerate((
        (1, 0, 0x01),   # halfword
        (2, 0, 0x01),   # word
        (3, 0, 0x01),   # doubleword
    )):
        await env.reset()
        await env.step(beat(((0, entry(0, active=active_mask, valid=active_mask,
                                      deew=deew, nf=nf)),)))
        await env.step(beat(lsu_ready=(True, True, True)))
    # Aligned, reachable wide next-element site 12 (lane 0): seven e32
    # fields, first continuation starts at field 4 and leaves 12 bytes.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x1000, valid=0x1001, deew=2,
        ieew=2, nf=6, start_field=4)),)))
    await env.step(beat(lsu_ready=(True, True, True)))

    # The segment-7/e32 index offset has a dedicated decoder arm.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x10, valid=0x10, nf=6,
                                  deew=0, ieew=2, uop=4, op2=0x03020100)),)))
    await env.step(beat(lsu_ready=(True, True, True)))

    # Ordinary indexed addressing carries nonzero recovery and queue metadata;
    # this is distinct from the segment-7/e32 decoder case above.
    await env.reset()
    await env.step(beat(((0, entry(
        0, active=0x04, valid=0x04, uop=4, ieew=1,
        op2=0x00000000000000000000000000030002,
        ftq_flag=1, ftq=42, ftq_off=17, lq_flag=1, lq=5,
        sq_first=1, sq_second=1, sq=7,
    )),)))
    await env.step(beat(lsu_ready=(True, True, True)))

    # Select higher sites so all three active lanes and the empty low/high
    # selectors carry nonzero offsets.  This also exercises both lane-1/2
    # data-size muxes and the two-byte empty issue path.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x4000, valid=0x5555, deew=1, ieew=1)),)))
    await env.step(beat(lsu_ready=(True, True, True)))
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x0000, valid=0x5555, ack=0x0555,
                                  deew=1, ieew=1)),)))
    await env.step(beat(empty_ready=(True, True)))

    # Verify circular load/store pointer increments at their wrap boundaries.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x02, valid=0x02, lq=119)),)))
    await env.step(beat(lsu_ready=(True, True, True)))
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x02, valid=0x02, uop=1,
                                  sq_first=0, sq_second=1, sq=63)),)))
    await env.step(beat(lsu_ready=(True, True, True)))
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x00, valid=0x02, lq=119)),)))
    await env.step(beat(empty_ready=(True, True)))

    # Walk every byte position once for each producer domain.  The micro-
    # architectural behavior is still one active/empty element selection per
    # cycle; the sweep makes the generated priority encoders observable at
    # every legal position rather than relying on a random mask.
    for site in range(16):
        await env.reset()
        mask = 1 << site
        await env.step(beat(((0, entry(0, active=mask, valid=mask)),)))
        await env.step(beat(lsu_ready=(True, True, True)))
    for site in range(16):
        await env.reset()
        mask = 1 << site
        await env.step(beat(((0, entry(0, active=0, valid=mask)),)))
        await env.step(beat(empty_ready=(True, True)))

    # Put a wide element on each of the secondary active lanes.  The ordinary
    # site sweep above mostly selects lane 0; these two legal cases exercise
    # lane-1/lane-2 data-mask and wider-than-128 mux arms.
    for mask, valid_mask, field in ((0x10, 0x11, 4), (0x100, 0x101, 3)):
        await env.reset()
        await env.step(beat(((0, entry(
            0, active=mask, valid=valid_mask, nf=4, deew=2, ieew=2,
            start_field=field, uop=0,
        )),)))
        await env.step(beat(lsu_ready=(True, True, True)))

    # Empty-stage element generation has the same wide and segment-7/e32
    # decoder arms as the active stage.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0, valid=0x1001, nf=6, deew=2,
                                  ieew=2, start_field=4)),)))
    await env.step(beat(empty_ready=(True, True)))
    await env.reset()
    await env.step(beat(((0, entry(0, active=0, valid=0x10, nf=6,
                                  deew=0, ieew=2, uop=4)),)))
    await env.step(beat(empty_ready=(True, True)))

    env.coverage.group.assert_coverage(100)
    assert env.checker.board.status.failed == 0
