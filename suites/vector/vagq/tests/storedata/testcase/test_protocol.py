"""StoreDataCtrl real-DUT scenarios driven by acknowledged store entries."""
from vagqverify.storedata.types import Beat, Entry, Redirect, VrfReadResponse


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def entry(index=0, *, active=0xffff, ack=0, sent=0, deew=0,
          start=0, rob=32, rob_flag=0, sq_first=0, sq_second=0,
          sq=3, psrc=16, uop=1, permit=True):
    return Entry(
        valid=True,
        uop_type=uop,
        rob_flag=rob_flag,
        rob_value=rob,
        psrc2=psrc + index,
        deew=deew,
        start_byte=start,
        elem_active=active,
        req_ack=ack,
        data_sent=sent,
        state=3,
        sq_first_flag=sq_first,
        sq_second_flag=sq_second,
        sq_value=sq + index,
        ordered_can_proceed=permit,
    )


def beat(entries=(), *, psrc_ready=(), redirect=Redirect(),
         req_ready=False, response=VrfReadResponse(), store_ready=(False, False),
         blocked=()):
    values = [Entry() for _ in range(8)]
    ready = [False] * 8
    for index, value in entries:
        values[index] = value
        ready[index] = True
    for index in psrc_ready:
        ready[index] = True
    for index in blocked:
        ready[index] = False
    return Beat(
        entries=tuple(values),
        psrc2_ready=tuple(ready),
        redirect=redirect,
        older_matrix=matrix(),
        vrf_read_req_ready=req_ready,
        vrf_read_resp=response,
        store_data_ready=store_ready,
    )


def response(entry_idx, rob, data=0x112233445566778899aabbccddeeff00, *, flag=0):
    return VrfReadResponse(True, entry_idx, flag, rob, data)


async def test_storedata_two_slot_residency_progress_and_redirect(storedata_env):
    env = storedata_env
    await env.reset()

    await env.step(beat())

    # No STA ACK means no VRF prefetch; psrc2Ready and redirect are separate
    # admission gates.
    await env.step(beat(((0, entry(0, ack=0)),), req_ready=True))
    await env.step(beat(((0, entry(0, ack=1)),), req_ready=False, blocked=(0,)))
    await env.step(beat(
        ((0, entry(0, ack=1)),),
        req_ready=True,
    ))

    # The read remains pending for a cycle before the mismatched response.
    await env.step(beat(((0, entry(0, ack=1)),)))

    # A wrong-ROB response is stale and leaves the read pending; redirect then
    # cancels the pending transaction without creating a resident slot.
    await env.step(beat(
        ((0, entry(0, ack=1)),),
        response=response(0, 33),
    ))
    await env.step(beat(
        ((0, entry(0, ack=1)),),
        redirect=Redirect(True, 1, 0, 32),
    ))

    # Establish slot 0 and hold its first flow under downstream backpressure.
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x03, ack=0x03)),), req_ready=True))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03)),),
        response=response(0, 32),
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03)),),
        store_ready=(False, False),
    ))

    # The first fire is reflected by the next-cycle external dataSent view;
    # the cached slot then advances to the next acknowledged byte.
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x00)),),
        store_ready=(True, False),
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),),
        store_ready=(False, False),
    ))

    # A second entry occupies the other slot while entry 0 remains resident;
    # both public store-data outputs can then fire independently.
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),
         (1, entry(1, active=0x03, ack=0x03, rob=33))),
        req_ready=True,
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),
         (1, entry(1, active=0x03, ack=0x03, rob=33))),
        response=response(1, 33),
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),
         (1, entry(1, active=0x03, ack=0x03, rob=33))),
        store_ready=(False, True),
    ))

    # Permission revocation suppresses a resident flow without losing its
    # slot; restoring permission allows the next byte to progress.
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, permit=False)),
         (1, entry(1, active=0x03, ack=0x03, rob=33, sent=0x01, permit=False))),
        store_ready=(False, False),
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),
         (1, entry(1, active=0x03, ack=0x03, rob=33, sent=0x01))),
        store_ready=(True, True),
    ))

    # A matching redirect flushes both resident entries and cannot produce a
    # late data update.
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x03, sent=0x01)),
         (1, entry(1, active=0x03, ack=0x03, rob=33, sent=0x01))),
        redirect=Redirect(True, 1, 0, 32),
        store_ready=(True, True),
    ))

    # A completed slot is reusable for a different candidate; a slot with no
    # currently ACKed-unsent byte is reusable even when its active mask is not
    # yet complete.  Both cases are observed before the replacement read.
    await env.reset()
    await env.step(beat(((0, entry(0, active=1, ack=1)),), req_ready=True))
    await env.step(beat(
        ((0, entry(0, active=1, ack=1)),),
        response=response(0, 32),
    ))
    await env.step(beat(
        ((0, entry(0, active=1, ack=1, sent=1)),
         (1, entry(1, active=1, ack=1, rob=33))),
        req_ready=True,
    ))
    await env.reset()
    await env.step(beat(((0, entry(0, active=0x03, ack=0x01)),), req_ready=True))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x01)),),
        response=response(0, 32),
    ))
    await env.step(beat(
        ((0, entry(0, active=0x03, ack=0x01, sent=1)),
         (1, entry(1, active=1, ack=1, rob=33))),
        req_ready=True,
    ))

    # Cover all legal EEW repetition modes and the distinction between a full,
    # sparse, start-offset and partial ACK flow.  Each case uses an actual VRF
    # read/response transaction rather than a direct store-data oracle.
    for deew, active, ack, start in (
        (0, 0xffff, 0xffff, 0),
        (1, 0x55, 0x55, 0),
        (2, 0x1111, 0x1111, 0),
        (3, 0x0101, 0x0101, 0),
        (0, 0x0501, 0x0501, 4),
        (1, 0x0003, 0x0001, 0),
    ):
        await env.reset()
        await env.step(beat(((0, entry(0, active=active, ack=ack,
                                      deew=deew, start=start)),), req_ready=True))
        await env.step(beat(
            ((0, entry(0, active=active, ack=ack, deew=deew, start=start)),),
            response=response(0, 32, data=0x00112233445566778899aabbccddeeff),
            store_ready=(True, False),
        ))

    # Candidate flush is distinct from a resident flush; no request is issued
    # for a valid but redirected entry.
    await env.reset()
    await env.step(beat(
        ((2, entry(2, active=1, ack=1, rob=50)),),
        redirect=Redirect(True, 1, 0, 50),
        req_ready=True,
    ))

    # Exercise every low-bit pending selector for both resident slots.  The
    # public behavior is still one flow per cycle; this directed site sweep
    # makes the generated priority encoder's legal byte positions observable.
    for site in range(16):
        mask = 1 << site
        await env.reset()
        await env.step(beat(
            ((0, entry(0, active=mask, ack=mask)),), req_ready=True
        ))
        await env.step(beat(
            ((0, entry(0, active=mask, ack=mask)),),
            response=response(0, 32),
            store_ready=(True, False),
        ))

    for site in range(16):
        mask = 1 << site
        await env.reset()
        await env.step(beat(
            ((0, entry(0, active=1, ack=1)),), req_ready=True
        ))
        await env.step(beat(
            ((0, entry(0, active=1, ack=1)),),
            response=response(0, 32),
        ))
        await env.step(beat(
            ((0, entry(0, active=1, ack=1)),
             (1, entry(1, active=mask, ack=mask, rob=33))),
            req_ready=True,
        ))
        await env.step(beat(
            ((0, entry(0, active=1, ack=1)),
             (1, entry(1, active=mask, ack=mask, rob=33))),
            response=response(1, 33),
            store_ready=(False, True),
        ))

    # Fill both resident slots with all-one VRF data, drain them, then reuse
    # both slots with zero data.  This makes every slot-data and slot-metadata
    # payload bit observe a real 1->0 transition through the public protocol.
    await env.reset()
    first = (
        (0, entry(0, active=1, ack=1, rob=60)),
        (1, entry(1, active=1, ack=1, rob=61)),
    )
    await env.step(beat(first, req_ready=True))
    await env.step(beat(first, response=response(0, 60, data=0xffffffffffffffffffffffffffffffff)))
    await env.step(beat(first, response=response(1, 61, data=0xffffffffffffffffffffffffffffffff)))
    await env.step(beat(first, store_ready=(True, True)))
    await env.step(beat(
        ((0, entry(0, active=1, ack=1, sent=1, rob=60)),
         (1, entry(1, active=1, ack=1, sent=1, rob=61)),),
        store_ready=(True, True),
    ))
    second = (
        (0, entry(0, active=1, ack=1, rob=62)),
        (1, entry(1, active=1, ack=1, rob=63)),
    )
    await env.step(beat(second, req_ready=True))
    await env.step(beat(second, response=response(0, 62, data=0)))
    await env.step(beat(second, response=response(1, 63, data=0)))
    await env.step(beat(second, store_ready=(True, True)))

    env.coverage.group.assert_coverage(100)
    assert env.checker.board.status.failed == 0
