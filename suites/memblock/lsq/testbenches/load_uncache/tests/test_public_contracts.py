"""Small semantic oracles, deliberately independent of the existing models."""

import pytest


@pytest.mark.parametrize("review_dut", ["load_queue_uncache"], indirect=True)
@pytest.mark.parametrize("mode", ("reuse_unconsumed", "different_sid", "consume_first"))
@pytest.mark.parametrize("new_error", (False, True))
async def test_returned_SID_cannot_rewrite_original_response(review_dut, mode, new_error):
    e = review_dut
    e.metadata = dict(issue="LQU-SID-001", mode=mode, new_error=new_error,
        domain="Normal NC LQU input projection; native Uncache allocator and full LoadUnit not instantiated")
    a, b = dict(uid=1, rob=10, lq=11, va=0x10000, pa=0x80000000), dict(uid=2, rob=11, lq=12, va=0x11000, pa=0x80001000)
    data_a, data_b = 0x0123456789ABCDEF, 0xFEDCBA9876543210
    active_sids = {}

    async def enqueue(owner, lane):
        await e.enqueue(owner, lane, pending=e.pending)
        e.check("LQU valid input actually sampled", e.request_input_valid(lane), True)
        e.event("LDU_S3_input", uid=owner["uid"], ROB=owner["rob"], LQ=owner["lq"],
                PA=owner["pa"], VA=owner["va"], mask=255, cause="C_UNCACHE", input_lane=lane)

    async def take_and_bind(owner, sid):
        mid = await e.bus_fire(sid, owner)
        assert sid not in active_sids, "SID reuse only after original external response was returned"
        active_sids[sid] = owner["uid"]
        e.event("original_PA_consumed_by_bus", uid=owner["uid"], mid=mid, PA=owner["pa"])

    async def respond(owner, sid, data, error):
        assert active_sids.pop(sid) == owner["uid"]
        await e.respond(owner, sid, data, error=error)

    async def consume(owner, data, error):
        packet = await e.bypass(1, owner)
        e.check("defined s1 response", packet.bypass[1].s1_valid, True)
        e.check("s1 PA belongs to original UID", packet.bypass[1].s1_paddr, owner["pa"])
        s1_error = packet.exception.exceptions >> 19 & 1
        e.check("exception event valid", packet.exception.valid, True)
        e.event("original_UID_s1_consume", uid=owner["uid"], original_PA=owner["pa"], actual_error=s1_error)
        await e.idle(1)
        actual = dict(data=e.post_response.bypass[1].s2_data,
                      derr=e.post_response.bypass[1].s2_derr,
                      nderr=e.post_response.bypass[1].s2_nderr, s1_error=s1_error)
        expected = dict(data=data * ((1 << 64) + 1), derr=int(error), nderr=0, s1_error=int(error))
        e.event("original_UID_s2_response", uid=owner["uid"], **actual)
        e.check("original response preserved at actual consumption", actual, expected, fatal=False)
        await e.idle(1)

    await enqueue(a, 0)
    await take_and_bind(a, 3)
    await respond(a, 3, data_a, False)
    if mode == "consume_first":
        await consume(a, data_a, False)
    await enqueue(b, 1)
    sid_b = 4 if mode == "different_sid" else 3
    await take_and_bind(b, sid_b)
    await respond(b, sid_b, data_b, new_error)
    if mode != "consume_first":
        await consume(a, data_a, False)
    await consume(b, data_b, new_error)
    await e.idle(5)
    e.check("all external responses returned", active_sids, {})
    e.finish()
