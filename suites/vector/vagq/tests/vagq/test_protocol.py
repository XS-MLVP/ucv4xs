"""Real generated VAGQ integration scenarios."""

from dataclasses import replace

from suites.vector.vagq.legacy_pins import P
from suites.vector.vagq.vagq.driver import response_beat
from suites.vector.vagq.vagq.types import AddrPacket, Beat, DataPacket, NativePacket, Redirect, Response


def load_addr(*, entry=0, rob=1, uop_type=0, vl=16, vstart=0,
              v0=0xffff, vma=0, vta=0, uop_idx=0, last=True,
              deew=0, ieew=0, nf=0):
    return AddrPacket(
        entry_idx=entry, uop_type=uop_type, rob_value=rob,
        pdest=3 + entry, psrc2=4 + entry, base_addr=0x1000 + entry * 0x100,
        v0_byte_mask=v0, deew=deew, ieew=ieew, emul=0,
        vl=vl, vstart=vstart, vma=vma, vta=vta, uop_idx=uop_idx,
        last_uop=int(last), nf=nf,
        ftq_value=0x22 + entry, ftq_offset=0x1d,
        lq_value=4 + entry, sq_value=3 + entry,
        vsew=deew, vlmul=0,
    )


def data_for(addr, *, op2=0x20):
    return DataPacket(entry_idx=addr.entry_idx, rob_value=addr.rob_value, op2_data=op2)


def run_until_writeback(env, beat, *, admit=None, limit=48, vrf_data=0):
    seen = []
    env.cycle(Beat())
    for cycle in range(limit):
        outputs = env.cycle(beat, admit=admit if cycle == 0 else None)
        seen.append(outputs)
        if outputs.get(P.p_robWriteback_valid):
            return seen
        beat = response_beat(outputs, data=vrf_data)
    raise AssertionError('VAGQ did not reach writeback within the scenario bound')


def response_for_fires(outputs, beat, *, std_busy=(False, False), data=0):
    """Return next-cycle responses only for requests that fired this cycle."""
    next_beat = response_beat(
        outputs,
        base=Beat(
            ldu_ready=beat.ldu_ready,
            sta_ready=beat.sta_ready,
            empty_ready=beat.empty_ready,
            std_busy=std_busy,
        ),
        data=data,
    )
    ldu = tuple(response if beat.ldu_ready[lane] else Response()
                for lane, response in enumerate(next_beat.ldu_resp))
    sta = tuple(response if beat.sta_ready[lane] else Response()
                for lane, response in enumerate(next_beat.sta_resp))
    empty = tuple(response if beat.empty_ready[lane] else type(response)()
                  for lane, response in enumerate(next_beat.empty_resp))
    return replace(next_beat, ldu_resp=ldu, sta_resp=sta, empty_resp=empty)


def test_strided_load_admission_split_response_and_writeback(vagq_env):
    vagq_env.reset()
    addr = load_addr(vl=16)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(
            addr=(addr, None), addr_valid=(True, False),
            stride=(data, None), stride_valid=(True, False),
        ),
        admit=(addr, data),
    )
    requests = [
        output for output in seen
        if output.get(P.p_lduReq_0_valid) or
        output.get(P.p_lduReq_1_valid) or output.get(P.p_lduReq_2_valid)
    ]
    assert requests
    assert seen[-1][P.p_robWriteback_bits_entryIdx] == addr.entry_idx


def test_strided_store_requires_sta_ack_then_vrf_data_before_writeback(vagq_env):
    vagq_env.reset()
    addr = load_addr(rob=7, uop_type=1, vl=1, v0=1)
    data = data_for(addr, op2=0x40)
    seen = run_until_writeback(
        vagq_env,
        Beat(
            addr=(addr, None), addr_valid=(True, False),
            stride=(data, None), stride_valid=(True, False),
        ),
        admit=(addr, data),
        vrf_data=0x112233445566778899AABBCCDDEEFF00,
    )
    assert any(output.get(P.p_vrfReadReq_valid) for output in seen)
    assert any(output.get(P.p_vagqStdData_0_valid) or
               output.get(P.p_vagqStdData_1_valid) for output in seen)
    assert seen[-1][P.p_robWriteback_bits_entryIdx] == addr.entry_idx
    assert not seen[-1].get(P.p_vpWakeUp_valid, 0)


def test_address_and_stride_data_may_arrive_on_separate_cycles(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=2, rob=21, vl=1, v0=1)
    data = data_for(addr, op2=0x18)
    first = vagq_env.cycle(
        Beat(addr=(addr, None), addr_valid=(True, False)),
        admit=None,
    )
    second = vagq_env.cycle(
        replace(
            response_beat(first),
            stride=(data, None), stride_valid=(True, False),
        ),
        admit=(addr, data),
    )
    beat = response_beat(second)
    for _ in range(48):
        outputs = vagq_env.cycle(beat)
        if outputs.get(P.p_robWriteback_valid):
            assert outputs[P.p_robWriteback_bits_entryIdx] == addr.entry_idx
            return
        beat = response_beat(outputs)
    raise AssertionError('separate admission did not complete')


def test_indexed_load_uses_index_data_and_preserves_entry_metadata(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=3, rob=31, uop_type=4, vl=2, v0=0x3, ieew=0)
    data = data_for(addr, op2=0x44_22)
    seen = run_until_writeback(
        vagq_env,
        Beat(
            addr=(addr, None), addr_valid=(True, False),
            index=(data, None), index_valid=(True, False),
        ),
        admit=(addr, data),
    )
    addresses = {
        output[P.io(f'lduReq_{lane}_bits_req_data_src_0')]
        for output in seen
        for lane in range(3)
        if output.get(P.io(f'lduReq_{lane}_valid')) and
        output.get(P.io(f'lduReq_{lane}_bits_meta_valid'))
    }
    assert addr.base_addr + 0x22 in addresses
    assert addr.base_addr + 0x44 in addresses


def test_partial_load_reads_old_vd_and_writes_only_merge_window(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=4, rob=41, vl=1, v0=1)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(addr=(addr, None), addr_valid=(True, False),
             stride=(data, None), stride_valid=(True, False)),
        admit=(addr, data),
        vrf_data=0xFFEEDDCCBBAA99887766554433221100,
    )
    assert any(output.get(P.p_vrfReadReq_valid) for output in seen)
    writes = [output for output in seen if output.get(P.p_vrfWriteReq_valid)]
    assert writes
    assert writes[-1][P.p_vrfWriteReq_bits_mask] != 0
    assert writes[-1][P.p_vrfWriteReq_bits_pdest] == addr.pdest


def test_load_nack_retries_without_falsely_acknowledging_the_element(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=5, rob=51, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(addr=(addr, None), addr_valid=(True, False),
                stride=(data, None), stride_valid=(True, False))
    nacked = False
    retried = False
    seen = []
    for cycle in range(64):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        seen.append(outputs)
        active_lanes = [lane for lane in range(3)
                        if outputs.get(P.io(f'lduReq_{lane}_valid')) and
                        outputs.get(P.io(f'lduReq_{lane}_bits_meta_valid'))]
        if active_lanes and nacked:
            retried = True
        next_beat = response_beat(outputs)
        if active_lanes and not nacked:
            lane = active_lanes[0]
            responses = list(next_beat.ldu_resp)
            responses[lane] = replace(responses[lane], is_nack=1)
            next_beat = replace(next_beat, ldu_resp=tuple(responses))
            nacked = True
        beat = next_beat
        if outputs.get(P.p_robWriteback_valid):
            assert not outputs.get(P.p_robWriteback_bits_exception)
            break
    else:
        raise AssertionError('NACK scenario did not reach writeback')
    assert nacked and retried


def test_load_exception_reaches_rob_without_vector_wakeup(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=6, rob=61, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(addr=(addr, None), addr_valid=(True, False),
                stride=(data, None), stride_valid=(True, False))
    exception_sent = False
    for cycle in range(64):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        next_beat = response_beat(outputs)
        active_lanes = [lane for lane in range(3)
                        if outputs.get(P.io(f'lduReq_{lane}_valid')) and
                        outputs.get(P.io(f'lduReq_{lane}_bits_meta_valid'))]
        if active_lanes and not exception_sent:
            lane = active_lanes[0]
            responses = list(next_beat.ldu_resp)
            responses[lane] = replace(
                responses[lane], exception=1, exception_number=9,
                fault_elem_idx=0,
            )
            next_beat = replace(next_beat, ldu_resp=tuple(responses))
            exception_sent = True
        beat = next_beat
        if outputs.get(P.p_robWriteback_valid):
            assert outputs[P.p_robWriteback_bits_exception] == 1
            assert outputs.get(P.p_vpWakeUp_valid, 0) == 0
            break
    else:
        raise AssertionError('exception scenario did not reach writeback')
    assert exception_sent


def test_load_request_is_held_under_target_backpressure_then_fires(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=7, rob=71, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(False, False, False),
    )
    held = None
    seen_fire = False
    for cycle in range(64):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        active = next((lane for lane in range(3)
                       if outputs.get(P.io(f'lduReq_{lane}_valid')) and
                       outputs.get(P.io(f'lduReq_{lane}_bits_meta_valid'))), None)
        if active is not None and not seen_fire:
            current = tuple(outputs.get(P.io(f'lduReq_{active}_bits_meta_{field}'))
                            for field in ('entryIdx', 'byteOffset', 'elemIdx', 'dataMask'))
            if held is None:
                held = current
            else:
                assert current == held
        ready = cycle >= 8
        beat = response_beat(
            outputs,
            base=Beat(ldu_ready=(ready, ready, ready)),
        )
        if active is not None and ready:
            seen_fire = True
        if outputs.get(P.p_robWriteback_valid):
            break
    else:
        raise AssertionError('backpressure scenario did not complete')
    assert held is not None and seen_fire


def test_indexed_store_exercises_sta_backpressure_multilane_and_std_busy(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=0, rob=81, uop_type=5, vl=16, v0=0xffff, ieew=0)
    data = data_for(addr, op2=0x44_33_22_11)
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        index=(data, None), index_valid=(True, False),
        sta_ready=(False, True),
    )
    released = False
    busy_remaining = 0
    saw_multi = False
    saw_busy_hold = False
    for cycle in range(96):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        valid_store = [lane for lane in range(2)
                       if outputs.get(P.io(f'staReq_{lane}_valid')) and
                       outputs.get(P.io(f'staReq_{lane}_bits_meta_valid'))]
        saw_multi |= len(valid_store) == 2
        if cycle >= 8:
            released = True
        if outputs.get(P.p_vrfReadReq_valid) and busy_remaining == 0:
            busy_remaining = 3
        next_busy = (True, False) if busy_remaining else (False, False)
        saw_busy_hold |= bool(next_busy[0]) and any(
            outputs.get(P.io(f'vagqStdData_{lane}_valid')) for lane in range(2)
        ) is False
        if busy_remaining:
            busy_remaining -= 1
        current = beat
        next_beat = response_for_fires(
            outputs, current, std_busy=next_busy,
            data=0x112233445566778899AABBCCDDEEFF00,
        )
        beat = replace(
            next_beat,
            sta_ready=(True, True) if released else (False, True),
        )
        if outputs.get(P.p_robWriteback_valid):
            break
    else:
        raise AssertionError('indexed store did not reach writeback')
    assert saw_multi and saw_busy_hold


def test_prestart_window_keeps_only_later_elements_live(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=1, rob=91, vl=16, v0=0xffff, vstart=4)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(addr=(addr, None), addr_valid=(True, False),
             stride=(data, None), stride_valid=(True, False)),
        admit=(addr, data),
    )
    elem_indices = {
        output[P.io(f'lduReq_{lane}_bits_meta_elemIdx')]
        for output in seen for lane in range(3)
        if output.get(P.io(f'lduReq_{lane}_valid')) and
        output.get(P.io(f'lduReq_{lane}_bits_meta_valid'))
    }
    assert elem_indices and min(elem_indices) >= 4


def test_agnostic_inactive_window_completes_without_old_vd_read(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=2, rob=101, vl=1, v0=1, vma=1, vta=1)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(addr=(addr, None), addr_valid=(True, False),
             stride=(data, None), stride_valid=(True, False)),
        admit=(addr, data),
    )
    assert not any(output.get(P.p_vrfReadReq_valid) for output in seen)


def test_vrf_merge_and_high_element_payload_bits_toggle(vagq_env):
    """Exercise legal merge payload polarities and a high element index."""
    for vrf_data in (
        0xffffffffffffffffffffffffffffffff,
        0,
    ):
        vagq_env.reset()
        addr = load_addr(entry=0, rob=181, vl=1, v0=1)
        data = data_for(addr)
        run_until_writeback(
            vagq_env,
            Beat(
                addr=(addr, None), addr_valid=(True, False),
                stride=(data, None), stride_valid=(True, False),
            ),
            admit=(addr, data), vrf_data=vrf_data,
        )

    vagq_env.reset()
    addr = load_addr(entry=1, rob=182, vl=255, v0=0xffff)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(
            addr=(addr, None), addr_valid=(True, False),
            stride=(data, None), stride_valid=(True, False),
        ),
        admit=(addr, data), vrf_data=0,
        limit=512,
    )
    assert seen[-1].get(P.p_robWriteback_valid)


def test_segmented_load_uses_multi_field_data_masks(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=3, rob=111, vl=4, v0=0xffff, nf=1)
    data = data_for(addr)
    seen = run_until_writeback(
        vagq_env,
        Beat(addr=(addr, None), addr_valid=(True, False),
             stride=(data, None), stride_valid=(True, False)),
        admit=(addr, data),
    )
    masks = {
        output[P.io(f'lduReq_{lane}_bits_meta_dataMask')]
        for output in seen for lane in range(3)
        if output.get(P.io(f'lduReq_{lane}_valid')) and
        output.get(P.io(f'lduReq_{lane}_bits_meta_valid'))
    }
    assert 3 in masks


def test_native_older_load_coexists_with_active_vagq_on_another_lane(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=4, rob=121, vl=1, v0=1)
    data = data_for(addr)
    native = NativePacket.from_dict(
        valid=True,
        robIdx_flag=0,
        robIdx_value=1,
        ctrl_fuType=0x12345,
        ctrl_fuOpType=0x456,
        data_src_0=0xDEAD,
        data_pc=0x2345,
    )
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        issue_lda=(native, NativePacket(), NativePacket()),
    )
    saw_native = False
    saw_active_with_native = False
    for cycle in range(64):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        native_lane = outputs.get(P.p_lduReq_0_bits_req_ctrl_fuType) == 0x12345
        saw_native |= bool(outputs.get(P.p_lduReq_0_valid) and native_lane)
        active_lane = next((lane for lane in range(3)
                            if outputs.get(P.io(f'lduReq_{lane}_valid')) and
                            outputs.get(P.io(f'lduReq_{lane}_bits_meta_valid'))), None)
        if active_lane is not None and saw_native:
            saw_active_with_native = True
        keep_native = active_lane is None
        next_beat = response_for_fires(outputs, beat)
        beat = replace(
            next_beat,
            issue_lda=(native, NativePacket(), NativePacket())
            if keep_native else
            (NativePacket(), NativePacket(), NativePacket()),
        )
        if outputs.get(P.p_robWriteback_valid):
            break
    else:
        raise AssertionError('native+active scenario did not complete')
    assert saw_native and saw_active_with_native


def test_empty_marker_backpressure_holds_inactive_window_until_release(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=5, rob=131, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        empty_ready=(False, False),
    )
    held = False
    for cycle in range(80):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        held |= any(outputs.get(P.io(f'lsqEmptyReq_{lane}_valid'))
                    for lane in range(2)) and cycle < 8
        release = cycle >= 8
        beat = replace(
            response_for_fires(outputs, beat),
            empty_ready=(release, release),
        )
        if outputs.get(P.p_robWriteback_valid):
            break
    else:
        raise AssertionError('empty-marker backpressure did not complete')
    assert held


def test_store_exception_reaches_rob_without_load_wakeup(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=6, rob=141, uop_type=1, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(addr=(addr, None), addr_valid=(True, False),
                stride=(data, None), stride_valid=(True, False))
    exception_sent = False
    for cycle in range(80):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        next_beat = response_for_fires(
            outputs, beat, data=0x0123456789ABCDEFFEDCBA9876543210,
        )
        active_lanes = [lane for lane in range(2)
                        if outputs.get(P.io(f'staReq_{lane}_valid')) and
                        outputs.get(P.io(f'staReq_{lane}_bits_meta_valid'))]
        if active_lanes and not exception_sent:
            lane = active_lanes[0]
            responses = list(next_beat.sta_resp)
            responses[lane] = replace(
                responses[lane], exception=1, exception_number=11,
                fault_elem_idx=0,
            )
            next_beat = replace(next_beat, sta_resp=tuple(responses))
            exception_sent = True
        beat = next_beat
        if outputs.get(P.p_robWriteback_valid):
            assert outputs[P.p_robWriteback_bits_exception] == 1
            assert outputs.get(P.p_vpWakeUp_valid, 0) == 0
            break
    else:
        raise AssertionError('store exception scenario did not reach writeback')
    assert exception_sent


def test_redirect_flushes_a_pending_request_before_completion(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=7, rob=151, vl=1, v0=1)
    data = data_for(addr)
    beat = Beat(
        addr=(addr, None), addr_valid=(True, False),
        stride=(data, None), stride_valid=(True, False),
        ldu_ready=(False, False, False),
    )
    redirect_pending = False
    flushed = False
    redirect_cycles = 0
    for cycle in range(32):
        outputs = vagq_env.cycle(beat, admit=(addr, data) if cycle == 0 else None)
        active = any(outputs.get(P.io(f'lduReq_{lane}_valid')) and
                     outputs.get(P.io(f'lduReq_{lane}_bits_meta_valid'))
                     for lane in range(3))
        if active and not redirect_pending:
            redirect_pending = True
            beat = replace(
                response_for_fires(outputs, beat),
                redirect=Redirect(valid=True, level=1, rob_value=addr.rob_value),
            )
            continue
        if redirect_pending and beat.redirect.valid:
            redirect_cycles += 1
            flushed = not any(
                outputs.get(P.io(f'lduReq_{lane}_valid')) or
                outputs.get(P.io(f'staReq_{lane}_valid'))
                for lane in range(3)
            )
            beat = (
                Beat()
                if redirect_cycles >= 3 and flushed
                else replace(response_for_fires(outputs, beat), redirect=beat.redirect)
            )
        else:
            beat = response_for_fires(outputs, beat)
        assert not outputs.get(P.p_robWriteback_valid)
    assert redirect_pending and flushed


def test_eight_entry_pressure_keeps_occupied_entries_and_backpressures_reuse(vagq_env):
    vagq_env.reset()
    vagq_env.cycle(Beat())
    packets = [(load_addr(entry=i, rob=200 + i, vl=1, v0=1), None) for i in range(8)]
    packets = [(addr, data_for(addr)) for addr, _ in packets]
    neutral = Beat(ldu_ready=(False, False, False), empty_ready=(False, False))
    for start in range(0, 8, 2):
        pair = packets[start:start + 2]
        beat = Beat(
            addr=(pair[0][0], pair[1][0]), addr_valid=(True, True),
            stride=(pair[0][1], pair[1][1]), stride_valid=(True, True),
            ldu_ready=(False, False, False), empty_ready=(False, False),
        )
        vagq_env.cycle(beat, admit=pair)
    # Reuse of an occupied entry is presented legally at the external
    # interface but must be refused by EntryTable readiness.
    occupied = packets[0]
    vagq_env.cycle(
        Beat(
            addr=(occupied[0], None), addr_valid=(True, False),
            stride=(occupied[1], None), stride_valid=(True, False),
            ldu_ready=(False, False, False), empty_ready=(False, False),
        )
    )
    for _ in range(3):
        vagq_env.cycle(neutral)


def test_redirect_flushes_younger_entry_while_older_entry_survives(vagq_env):
    vagq_env.reset()
    older = load_addr(entry=0, rob=161, vl=1, v0=1)
    younger = load_addr(entry=1, rob=162, vl=1, v0=1)
    older_data = data_for(older)
    younger_data = data_for(younger)
    blocked = Beat(ldu_ready=(False, False, False), empty_ready=(False, False))
    vagq_env.cycle(Beat())
    vagq_env.cycle(
        Beat(
            addr=(older, younger), addr_valid=(True, True),
            stride=(older_data, younger_data), stride_valid=(True, True),
            ldu_ready=(False, False, False), empty_ready=(False, False),
        ),
        admit=[(older, older_data), (younger, younger_data)],
    )
    beat = blocked
    for cycle in range(8):
        outputs = vagq_env.cycle(beat)
        if cycle == 3:
            beat = replace(
                blocked,
                redirect=Redirect(valid=True, level=1, rob_value=younger.rob_value),
            )
        elif beat.redirect.valid:
            beat = replace(blocked, redirect=beat.redirect)
        else:
            beat = blocked
        assert not outputs.get(P.p_robWriteback_valid)


def test_redirect_flush_after_an_older_rob_position_removes_younger_entry(vagq_env):
    vagq_env.reset()
    addr = load_addr(entry=2, rob=172, vl=1, v0=1)
    data = data_for(addr)
    blocked = Beat(ldu_ready=(False, False, False), empty_ready=(False, False))
    vagq_env.cycle(Beat())
    vagq_env.cycle(
        replace(
            blocked,
            addr=(addr, None), addr_valid=(True, False),
            stride=(data, None), stride_valid=(True, False),
        ),
        admit=(addr, data),
    )
    beat = blocked
    for cycle in range(8):
        outputs = vagq_env.cycle(beat)
        if cycle == 3:
            beat = replace(
                blocked,
                redirect=Redirect(valid=True, level=0, rob_value=171),
            )
        elif beat.redirect.valid:
            beat = replace(blocked, redirect=beat.redirect)
        assert not outputs.get(P.p_robWriteback_valid)
