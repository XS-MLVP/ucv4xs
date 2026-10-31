"""EntryTable real-DUT lifecycle scenarios driven by semantic packets."""
from suites.vector.vagq.entrytable.types import (
    AddrPacket, Beat, DataPacket, MergeResp, Redirect, SplitReq,
    StateUpdate, StoreUpdate,
)


def addr(index, rob=10, *, uop=0, nf=0):
    return AddrPacket(entry_idx=index, rob_value=rob, uop_idx=uop, nf=nf, vl=1, base_addr=0x1000 + index)


def data(index, rob=10, value=0x1234):
    return DataPacket(entry_idx=index, rob_value=rob, op2_data=value)


def _addr_lane(packet, lane):
    return Beat(
        addr=(packet, None) if lane == 0 else (None, packet),
        addr_valid=(True, False) if lane == 0 else (False, True),
    )


def _data_lane(packet, lane, *, indexed=False):
    field = 'index' if indexed else 'data'
    values = {field: (packet, None) if lane == 0 else (None, packet),
              field + '_valid': (True, False) if lane == 0 else (False, True)}
    return Beat(**values)


async def test_entrytable_lifecycle_and_update_contract(entrytable_env):
    env = entrytable_env
    await env.reset()
    await env.step(Beat())

    # Address-only entry waits for data; the same entry's address is backpressured.
    await env.step(Beat(addr=(addr(0), None), addr_valid=(True, False)))
    await env.step(Beat(addr=(addr(0), None), addr_valid=(True, False)))
    await env.step(Beat(data=(data(0), None), data_valid=(True, False)))

    # Bitmap, earliest exception, dataSent, state transition and ROB clear.
    await env.step(Beat(split_req=(SplitReq(True, 1, 0x3), SplitReq())))
    await env.step(Beat(merge_resp=(
        MergeResp(1, set_req_ack=0x4, clear_req_sent=0x1, exception=True, exception_number=7, fault_elem_idx=4),
        MergeResp(1, exception=True, exception_number=3, fault_elem_idx=2),
        MergeResp(), MergeResp(), MergeResp(), MergeResp(), MergeResp(),
    )))
    await env.step(Beat(store_update=(StoreUpdate(True, 0, 0x8), StoreUpdate())))
    await env.step(Beat(split_done=StateUpdate(True, 1, 4)))
    await env.step(Beat(merge_done=StateUpdate(True, 1, 5)))
    await env.step(Beat(rob_clear=StateUpdate(True, 1, 0)))

    # Data-only and indexed-data-only entries begin in waitA.
    await env.step(Beat(data=(data(1, 21, 1), None), data_valid=(True, False)))
    # Keep the two source-specific qualification cases independent: the
    # registered age matrix has not yet observed a newly data-only entry.
    await env.reset()
    await env.step(Beat(index=(data(2, 22, 2), None), index_valid=(True, False)))

    # Address+data same-cycle enqueue enters split and redirect flushes it.
    await env.step(Beat(addr=(addr(3, 23), None), addr_valid=(True, False),
                         data=(data(3, 23, 3), None), data_valid=(True, False)))
    await env.step(Beat(redirect=Redirect(True, 1, 0, 23)))

    # Two physical entries from one ROB exercise same-ROB uop ordering/tie-break.
    await env.step(Beat(
        addr=(addr(4, 30, uop=0), addr(5, 30, uop=0)), addr_valid=(True, True),
        data=(data(4, 30, 4), data(5, 30, 5)), data_valid=(True, True),
    ))
    await env.step(Beat())

    # Exercise both issue lanes for every physical entry.  The address variants
    # also drive the embedded MaskGen through ordinary, segment, wide and
    # whole-window-prestart legal layouts; these are real EntryTable inputs,
    # not a standalone MaskGen qualification run.
    variants = (
        dict(deew=0, ieew=0, emul=0, nf=0, vl=1, vstart=0, vma=0, vta=0),
        dict(deew=1, ieew=0, emul=0, nf=0, vl=4, vstart=1, vma=1, vta=0),
        dict(deew=0, ieew=2, emul=0, nf=1, vl=16, vstart=0, vma=0, vta=1),
        dict(deew=0, ieew=2, emul=0, nf=6, vl=255, vstart=127, vma=1, vta=1),
    )
    for lane in (0, 1):
        await env.reset()
        for index in range(8):
            config = variants[index % len(variants)]
            await env.step(_addr_lane(AddrPacket(
                entry_idx=index, rob_value=100 + index, uop_type=index & 7,
                pdest=10 + index, psrc2=20 + index, base_addr=0x4000 + index,
                meta_ftq_flag=index & 1, meta_ftq_value=index,
                meta_ftq_offset=index + 1, meta_lq_flag=(index + 1) & 1,
                meta_lq_value=index + 2, meta_sq_first_flag=index & 1,
                meta_sq_second_flag=(index >> 1) & 1, meta_sq_value=index + 3,
                meta_vsew=index & 7, meta_vlmul=index & 7, **config), lane))
        await env.step(Beat())

    # Exercise data and indexed-data source priority independently on both
    # lanes.  Data-only entries are in waitA, so static address fields remain
    # intentionally unestablished until a later address packet.
    for indexed in (False, True):
        for lane in (0, 1):
            await env.reset()
            # Establish all ROB/uop metadata through address fires first.  The
            # subsequent source sweep then exercises every per-entry data
            # priority branch without making age depend on uninitialized
            # static fields of a newly data-only entry.
            for index in range(8):
                await env.step(_addr_lane(addr(index, 140 + index), 0))
            for index in range(8):
                await env.step(_data_lane(DataPacket(
                    entry_idx=index, rob_value=140 + index,
                    op2_data=(0x1000 + index) << (64 if lane else 0)),
                    lane, indexed=indexed))
            await env.step(Beat())

    # Fill all eight entries through both address/data lanes, then exercise
    # every per-entry dynamic update block.  This is deliberately separate
    # from the source-priority sweep so lifecycle assertions remain legal.
    await env.reset()
    for base in (0, 2, 4, 6):
        addresses = tuple(addr(index, 300 + index, uop=0)
                          for index in (base, base + 1))
        values = tuple(data(index, 300 + index, 0x100 + index)
                       for index in (base, base + 1))
        await env.step(Beat(addr=addresses, addr_valid=(True, True),
                            data=values, data_valid=(True, True)))
    await env.step(Beat())

    # With all entries live, select each of the five response positions once.
    # This covers the response-priority network for every entry, not just the
    # entry named by a one-hot response update.
    for slot in range(5):
        responses = [MergeResp() for _ in range(7)]
        responses[slot] = MergeResp(
            0xff, set_req_ack=0x0101, exception=True,
            exception_number=30 + slot, fault_elem_idx=6 - slot,
        )
        await env.step(Beat(merge_resp=tuple(responses)))

    for base in (0, 2, 4, 6):
        await env.step(Beat(split_req=(
            SplitReq(True, 1 << base, 1 << base),
            SplitReq(True, 1 << (base + 1), 1 << (base + 1)),
        )))

    for index in range(8):
        responses = tuple(
            MergeResp(
                1 << index,
                set_req_ack=1 << ((index + slot) & 15),
                clear_req_sent=1 << ((index + slot + 1) & 15),
                exception=True,
                exception_number=20 + slot,
                fault_elem_idx=8 - slot,
            ) for slot in range(5)
        ) + (MergeResp(), MergeResp())
        await env.step(Beat(merge_resp=responses))

    # A second, lower-fault response from slot 2 drives the selector's
    # response-2 arm for every entry.  It also verifies replacement of an
    # already-recorded exception by the earliest fault element.
    for index in range(8):
        responses = [MergeResp() for _ in range(7)]
        responses[2] = MergeResp(
            1 << index, set_req_ack=0x8000, exception=True,
            exception_number=55, fault_elem_idx=0,
        )
        await env.step(Beat(merge_resp=tuple(responses)))

    for base in (0, 2, 4, 6):
        await env.step(Beat(store_update=(
            StoreUpdate(True, base, 1 << base),
            StoreUpdate(True, base + 1, 1 << (base + 1)),
        )))
    await env.step(Beat(store_update=(
        StoreUpdate(), StoreUpdate(True, 0, 0x4000),
    )))

    for index in range(8):
        await env.step(Beat(split_done=StateUpdate(True, 1 << index, 4)))
    for index in range(8):
        await env.step(Beat(merge_done=StateUpdate(True, 1 << index, 5)))
    for index in range(8):
        await env.step(Beat(rob_clear=StateUpdate(True, 1 << index, 0)))

    env.coverage.group.assert_coverage(100)
    assert env.checker.board.status.failed == 0
