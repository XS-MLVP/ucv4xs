"""Independent combinational model of VAGQArbiter's grants and routing."""
from .schema import (
    LOAD_META_FIELDS,
    LOAD_REQ_FIELDS,
    OUTPUT_NAMES,
    STORE_META_FIELDS,
    STORE_REQ_FIELDS,
)
from .types import Beat, LsuReq, Observation


def _rob_after(left_flag, left_value, right_flag, right_value):
    return bool((left_flag ^ right_flag) ^ (left_value > right_value))


def _ptr_before(left_flag, left_value, right_flag, right_value):
    return bool((left_flag ^ right_flag) ^ (left_value < right_value))


def _ptr_equal(left_flag, left_value, right_flag, right_value):
    return left_flag == right_flag and left_value == right_value


def _sq_operation(first_flag, second_flag, value):
    return (second_flag << 6) | value


def _older(left: LsuReq, right: LsuReq, left_index: int, right_index: int, *, is_load: bool):
    same_rob = _ptr_equal(left.rob_flag, left.rob_value, right.rob_flag, right.rob_value)
    if is_load:
        older_queue = _ptr_before(left.lq_flag, left.lq_value, right.lq_flag, right.lq_value)
        same_queue = _ptr_equal(left.lq_flag, left.lq_value, right.lq_flag, right.lq_value)
    else:
        left_operation = _sq_operation(left.sq_first_flag, left.sq_second_flag, left.sq_value)
        right_operation = _sq_operation(right.sq_first_flag, right.sq_second_flag, right.sq_value)
        older_queue = _ptr_before(
            left.sq_first_flag, left_operation,
            right.sq_first_flag, right_operation,
        )
        same_queue = _ptr_equal(
            left.sq_first_flag, left_operation,
            right.sq_first_flag, right_operation,
        )
    older_element = older_queue or (same_queue and left_index < right_index)
    return older_element if same_rob else _rob_after(
        right.rob_flag, right.rob_value, left.rob_flag, left.rob_value
    )


def _oldest(active, requests, *, is_load):
    for left_index, present in enumerate(active):
        if not present:
            continue
        if all(
            (not active[right_index]) or left_index == right_index or _older(
                requests[left_index], requests[right_index], left_index, right_index,
                is_load=is_load,
            )
            for right_index in range(len(requests))
        ):
            return left_index
    return None


def _set_req(outputs, group, lane, fields, *, native=False):
    req_fields = LOAD_REQ_FIELDS if group == 'lduReq' else STORE_REQ_FIELDS
    for field in req_fields:
        outputs[f'io_{group}_{lane}_bits_req_{field}'] = fields.get(field, 0)


def _set_meta(outputs, group, lane, values, *, valid):
    fields = LOAD_META_FIELDS if group == 'lduReq' else STORE_META_FIELDS
    for field in fields:
        outputs[f'io_{group}_{lane}_bits_meta_{field}'] = values.get(field, 0) if valid else 0


def _active_req_fields(request: LsuReq, *, is_load: bool, fields):
    result = {field: 0 for field in fields}
    for name, value in {
        'data_src_0': request.vaddr,
        'data_pc': request.pc,
        'ctrl_isRVC': 0,
        'ctrl_ftqIdx_flag': request.ftq_flag,
        'ctrl_ftqIdx_value': request.ftq_value,
        'ctrl_ftqOffset': request.ftq_offset,
        'robIdx_flag': request.rob_flag,
        'robIdx_value': request.rob_value,
        'toRF_pdest': request.pdest if is_load else 0,
        'lqIdx_flag': request.lq_flag,
        'lqIdx_value': request.lq_value,
        'sqIdx_first_flag': request.sq_first_flag,
        'sqIdx_second_flag': request.sq_second_flag,
        'sqIdx_value': request.sq_value,
        'ctrl_vecWen': int(is_load),
    }.items():
        if name in result:
            result[name] = value
    return result


def _grant_lane(requests, native, lane_count, *, is_load):
    remaining = [request.valid and request.is_load == is_load for request in requests]
    grants = []
    for lane in range(lane_count):
        selected = _oldest(remaining, requests, is_load=is_load)
        if selected is not None and (
            not native[lane].valid
            or _rob_after(
                native[lane].get('robIdx_flag'),
                native[lane].get('robIdx_value'),
                requests[selected].rob_flag,
                requests[selected].rob_value,
            )
        ):
            grants.append(selected)
            remaining[selected] = False
        else:
            grants.append(None)
    return tuple(grants)


def observe(beat: Beat) -> Observation:
    load_grants = _grant_lane(beat.vagq_lsu, beat.issue_lda, 3, is_load=True)
    store_grants = _grant_lane(beat.vagq_lsu, beat.issue_sta, 2, is_load=False)
    outputs = {name: 0 for name in OUTPUT_NAMES}

    for lane in range(3):
        selected = load_grants[lane]
        native = beat.issue_lda[lane]
        selected_vagq = selected is not None
        valid = native.valid or selected_vagq
        outputs[f'io_lduReq_{lane}_valid'] = int(valid)
        outputs[f'io_issueLda_{lane}_ready'] = int(beat.ldu_ready[lane] and not selected_vagq)
        if selected_vagq:
            request = beat.vagq_lsu[selected]
            _set_req(
                outputs, 'lduReq', lane,
                _active_req_fields(request, is_load=True, fields=LOAD_REQ_FIELDS),
            )
            _set_meta(outputs, 'lduReq', lane, {
                'valid': 1,
                'entryIdx': request.entry_idx,
                'isLoad': 1,
                'byteOffset': request.byte_offset,
                'elemIdx': request.elem_idx,
                'dataSize': request.data_size,
                'dataMask': request.data_mask,
            }, valid=True)
        else:
            _set_req(outputs, 'lduReq', lane, native.values())
            _set_meta(outputs, 'lduReq', lane, {}, valid=False)

    for lane in range(2):
        selected = store_grants[lane]
        native = beat.issue_sta[lane]
        selected_vagq = selected is not None
        valid = native.valid or selected_vagq
        outputs[f'io_staReq_{lane}_valid'] = int(valid)
        outputs[f'io_issueSta_{lane}_ready'] = int(beat.sta_ready[lane] and not selected_vagq)
        if selected_vagq:
            request = beat.vagq_lsu[selected]
            _set_req(
                outputs, 'staReq', lane,
                _active_req_fields(request, is_load=False, fields=STORE_REQ_FIELDS),
            )
            _set_meta(outputs, 'staReq', lane, {
                'valid': 1,
                'entryIdx': request.entry_idx,
                'byteOffset': request.byte_offset,
                'elemIdx': request.elem_idx,
                'dataSize': request.data_size,
                'dataMask': request.data_mask,
            }, valid=True)
        else:
            _set_req(outputs, 'staReq', lane, native.values())
            _set_meta(outputs, 'staReq', lane, {}, valid=False)

    for lane in range(3):
        outputs[f'io_vagqLsuReq_{lane}_ready'] = int(
            any(grant == lane and beat.ldu_ready[target] for target, grant in enumerate(load_grants))
            or any(grant == lane and beat.sta_ready[target] for target, grant in enumerate(store_grants))
        )

    for lane, request in enumerate(beat.vagq_store_data):
        busy = beat.std_busy[lane]
        outputs[f'io_vagqStoreDataReq_{lane}_ready'] = int(not busy)
        outputs[f'io_vagqStdData_{lane}_valid'] = int(request.valid and not busy)
        outputs[f'io_vagqStdData_{lane}_bits_data'] = request.data
        outputs[f'io_vagqStdData_{lane}_bits_sqIdx_first_flag'] = request.sq_first_flag
        outputs[f'io_vagqStdData_{lane}_bits_sqIdx_second_flag'] = request.sq_second_flag
        outputs[f'io_vagqStdData_{lane}_bits_sqIdx_value'] = request.sq_value

    return Observation(outputs, load_grants, store_grants)
