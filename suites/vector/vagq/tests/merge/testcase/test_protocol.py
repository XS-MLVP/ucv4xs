"""MergeCtrl real-DUT scenarios for response, merge and writeback protocol."""
from vagqverify.merge.types import Beat, Entry, Redirect, Response


def matrix():
    return tuple(tuple(i < j for j in range(8)) for i in range(8))


def entry(index=0, *, state=4, uop=0, rob=32, pdest=40, psrc=50,
          merge_write=0xfffc, agnostic=0, active=0x03, ack=0xffff,
          sent=0, skip=False, exception=False, exception_number=0,
          fault=0, permit=True, deew=0, nf=0, uop_idx=0):
    return Entry(
        valid=True,
        uop_type=uop,
        rob_value=rob,
        pdest=pdest,
        psrc2=psrc,
        deew=deew,
        uop_idx=uop_idx,
        skip_merge=skip,
        elem_active=active,
        merge_write=merge_write,
        elem_agnostic=agnostic,
        nf=nf,
        req_ack=ack,
        data_sent=sent,
        exception=exception,
        exception_number=exception_number,
        fault_elem=fault,
        state=state,
        ordered_can_proceed=permit,
        lq_value=index,
        sq_value=index,
        vsew=1,
        vlmul=2,
        perf_eliminated=index & 1,
        perf_rename=100 + index,
        perf_dispatch=200 + index,
        perf_enq_rs=300 + index,
        perf_select=400 + index,
        perf_issue=500 + index,
        perf_runahead=600 + index,
        perf_tlb_first=700 + index,
        perf_tlb_resp=800 + index,
        debug_seq_num=0x1000 + index,
        debug_uop_idx=0x20 + index,
    )


def beat(entries=(), *, psrc_ready=(), ldu=(), sta=(), empty=(),
         read_ready=False, read_resp=None, redirect=Redirect()):
    values = [Entry() for _ in range(8)]
    ready = [False] * 8
    for index, value in entries:
        values[index] = value
    for index in psrc_ready:
        ready[index] = True
    if read_resp is None:
        read_valid, read_idx, read_flag, read_rob, read_data = False, 0, 0, 0, 0
    else:
        read_valid, read_idx, read_flag, read_rob, read_data = True, *read_resp
    return Beat(
        entries=tuple(values),
        psrc2_ready=tuple(ready),
        ldu_resp=tuple(ldu) if ldu else (Response(),) * 3,
        sta_resp=tuple(sta) if sta else (Response(),) * 2,
        empty_resp=tuple(empty) if empty else (Response(),) * 2,
        older_matrix=matrix(),
        vrf_read_req_ready=read_ready,
        vrf_read_resp_valid=read_valid,
        vrf_read_resp_entry_idx=read_idx,
        vrf_read_resp_rob_flag=read_flag,
        vrf_read_resp_rob_value=read_rob,
        vrf_read_resp_data=read_data,
        redirect=redirect,
    )


def response(index, mask, *, nack=False, exception=False, number=0, fault=0):
    return Response(True, index, mask, nack, exception, number, fault)


async def test_merge_response_old_vd_writeback_and_redirect(merge_env):
    env = merge_env
    await env.reset()
    await env.step(beat())

    # Response updates are combinational and independent of merge state:
    # normal ACK, NACK-clear, exception and empty-marker source are all public.
    await env.step(beat(
        ((0, entry()),),
        ldu=(response(0, 0x0003), Response(), response(0, 0x0004, nack=True)),
        empty=(response(0, 0x0008), Response()),
    ))
    await env.step(beat(
        ((0, entry()),),
        sta=(response(0, 0x0010, exception=True, number=7, fault=2), Response()),
    ))
    await env.step(beat(
        ((0, entry()),),
        ldu=(response(0, 1, nack=True), response(0, 2, nack=True), response(0, 4, nack=True)),
        sta=(response(0, 8, nack=True), response(0, 16, nack=True)),
        empty=(response(0, 32, nack=True), response(0, 64, nack=True)),
    ))

    # Isolate single-source and stale/redirect response bins.
    await env.reset()
    await env.step(beat(((0, entry()),), ldu=(response(0, 1), Response(), Response())))
    await env.step(beat(((0, entry()),), empty=(response(0, 2), Response())))
    await env.step(beat(
        ((0, entry()),),
        ldu=(response(0, 1), Response(), Response()),
        redirect=Redirect(True, 1, 0, 32),
    ))

    # splitDone has independent load-to-merge, store-to-wb and skip-to-wb
    # next-state behavior.
    await env.reset()
    await env.step(beat(((0, entry(state=3, uop=0, merge_write=0xfffc)),)))
    await env.reset()
    await env.step(beat(((0, entry(state=3, uop=1, merge_write=0xfffc, sent=0x03)),)))
    await env.reset()
    await env.step(beat(((0, entry(state=3, uop=0, skip=True, merge_write=0xfffc)),)))

    # Candidate priority and old-vd readiness are separate from the response
    # path; both candidates are eligible here and entry 0 is older.
    await env.reset()
    await env.step(beat(
        ((0, entry(merge_write=0, psrc=53)),
         (1, entry(1, merge_write=0, psrc=54, rob=33))),
        psrc_ready=(0, 1),
    ))
    await env.reset()
    await env.step(beat(((0, entry(merge_write=0xff, psrc=55)),)))

    # A split load requiring old vd performs read -> matching response -> write.
    await env.reset()
    merge_entry = entry(merge_write=0x00ff, agnostic=0x00f0, psrc=48)
    await env.step(beat(((0, merge_entry),), psrc_ready=(0,), read_ready=True))
    await env.step(beat(((0, merge_entry),), psrc_ready=(0,)))
    await env.step(beat(
        ((0, merge_entry),),
        psrc_ready=(0,),
        read_resp=(0, 0, 32, 0x00112233445566778899aabbccddeeff),
    ))
    await env.step(beat(((0, merge_entry),), psrc_ready=(0,)))
    await env.step(beat(((0, entry(state=5, merge_write=0x00ff, agnostic=0x00f0,
                                  psrc=48)),)))

    # No-old-vd merge starts from zero and still writes agnostic bytes.
    await env.reset()
    no_read = entry(merge_write=0, agnostic=0, psrc=49)
    await env.step(beat(((0, no_read),)))
    await env.step(beat(((0, entry(state=5, merge_write=0, agnostic=0,
                                  psrc=49)),)))

    # WB exception suppresses wakeup but still emits ROB clear/writeback.
    await env.reset()
    await env.step(beat(((0, entry(state=5, exception=True, exception_number=9,
                                  fault=4, pdest=60)),)))

    await env.reset()
    await env.step(beat(((0, entry(state=5, uop=1, skip=False)),)))
    await env.reset()
    await env.step(beat(((0, entry(state=5, skip=True)),)))

    await env.reset()
    await env.step(beat(((0, entry(merge_write=0xffff, agnostic=0xffff)),)))

    # A pending read is cancelled by redirect; a late response cannot create a
    # VRF write for the flushed owner.
    await env.reset()
    pending = entry(merge_write=0x00ff, agnostic=0, psrc=52)
    await env.step(beat(((0, pending),), psrc_ready=(0,), read_ready=True))
    await env.step(beat(
        ((0, pending),),
        redirect=Redirect(True, 1, 0, 32),
    ))
    await env.step(beat(
        ((0, pending),),
        read_resp=(0, 0, 32, 0x1234),
    ))

    await env.reset()
    await env.step(beat(
        ((0, entry(merge_write=0, rob=70)),),
        redirect=Redirect(True, 1, 0, 70),
    ))

    # Oldest merge choice and old-vd psrc blocking are distinct candidate
    # behaviors; entry 1 is not allowed to bypass an older blocked entry.
    await env.reset()
    await env.step(beat(
        ((0, entry(0, merge_write=0x00ff, psrc=54)),
         (1, entry(1, merge_write=0, psrc=55, rob=33))),
        psrc_ready=(),
    ))
    await env.step(beat(
        ((0, entry(0, merge_write=0x00ff, psrc=54)),
         (1, entry(1, merge_write=0, psrc=55, rob=33))),
    ))

    # Drive both polarities of the wide saved VRF response.  This is a
    # structural payload sweep attached to a legal old-Vd merge, not a direct
    # assignment to an internal merge register.
    for value in (0xffffffffffffffffffffffffffffffff, 0):
        await env.reset()
        pending = entry(merge_write=0x00ff, agnostic=0, psrc=57)
        await env.step(beat(((0, pending),), psrc_ready=(0,), read_ready=True))
        await env.step(beat(
            ((0, pending),),
            psrc_ready=(0,),
            read_resp=(0, 0, 32, value),
        ))
        await env.step(beat(((0, entry(state=5, merge_write=0x00ff, psrc=57)),)))

    for index in range(8):
        await env.reset()
        await env.step(beat(((index, entry(index, state=3, merge_write=0,
                                            ack=0xffff)),)))
    for index in range(8):
        await env.reset()
        await env.step(beat(((index, entry(index, state=5, uop=1)),)))

    env.coverage.group.assert_coverage(100)
    assert env.checker.board.status.failed == 0
