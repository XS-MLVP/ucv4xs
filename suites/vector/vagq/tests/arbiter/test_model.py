"""VAGQArbiter semantic qualification without DUT coverage credit."""
import pytest

from vagqverify.arbiter.model import _older, observe
from vagqverify.arbiter.types import Beat, LsuReq, NativeReq, StoreDataReq

pytestmark = pytest.mark.toffee_functional_coverage(False)


def active(index=0, **changes):
    values = dict(
        valid=True,
        entry_idx=index,
        rob_value=20 + index,
        is_load=True,
        lq_value=10 + index,
        sq_value=10 + index,
        elem_idx=8 + index,
        data_size=2,
        data_mask=0x00ff,
        pc=0x4000 + index,
        ftq_value=0x20 + index,
        ftq_offset=0x10 + index,
        byte_offset=index,
        vaddr=0x100000 + index * 8,
        pdest=30 + index,
        nf=0,
    )
    values.update(changes)
    return LsuReq(**values)


def native(valid=False, rob=0, **fields):
    return NativeReq.from_dict(
        valid=valid,
        robIdx_flag=fields.pop('robIdx_flag', 0),
        robIdx_value=rob,
        ctrl_fuType=0x55,
        ctrl_fuOpType=0x66,
        data_pc=0x7000,
        **fields,
    )


def beat(requests=(), **changes):
    values = [LsuReq() for _ in range(3)]
    for index, request in requests:
        values[index] = request
    return Beat(vagq_lsu=tuple(values), **changes)


def test_load_and_store_oldest_order_uses_queue_pointer_then_lane_tie():
    loads = (
        active(0, rob_value=50, lq_value=20),
        active(1, rob_value=50, lq_value=5),
        active(2, rob_value=50, lq_value=5),
    )
    observed = observe(Beat(vagq_lsu=loads, ldu_ready=(True, True, True)))
    assert observed.load_grants == (1, 2, 0)

    stores = (
        active(0, is_load=False, rob_value=50, sq_value=20),
        active(1, is_load=False, rob_value=50, sq_value=5),
        active(2, is_load=False, rob_value=50, sq_value=5),
    )
    observed = observe(Beat(vagq_lsu=stores, sta_ready=(True, True)))
    assert observed.store_grants == (1, 2)


def test_native_older_blocks_first_lane_but_next_lane_reserves_vagq():
    requests = (active(0, rob_value=20), LsuReq(), LsuReq())
    native_old = native(True, rob=10)
    observed = observe(Beat(
        vagq_lsu=requests,
        issue_lda=(native_old, NativeReq(), NativeReq()),
        ldu_ready=(True, True, True),
    ))
    assert observed.load_grants == (None, 0, None)
    assert observed.outputs['io_lduReq_0_bits_req_ctrl_fuType'] == 0x55
    assert observed.outputs['io_lduReq_1_bits_meta_entryIdx'] == 0
    assert observed.outputs['io_issueLda_0_ready'] == 1


def test_vagq_older_displaces_native_and_routes_all_active_metadata():
    request = active(
        3,
        rob_flag=1,
        rob_value=2,
        lq_flag=1,
        lq_value=7,
        sq_first_flag=1,
        sq_second_flag=1,
        sq_value=9,
        pc=0x12345,
        ftq_flag=1,
        ftq_value=0x2a,
        ftq_offset=0x1d,
        byte_offset=7,
        elem_idx=19,
        vaddr=0x123456789,
        pdest=61,
        data_size=3,
        data_mask=0x0f0f,
    )
    observed = observe(Beat(
        vagq_lsu=(request, LsuReq(), LsuReq()),
        issue_lda=(native(True, rob=1, robIdx_flag=0), NativeReq(), NativeReq()),
        ldu_ready=(False, True, True),
    ))
    assert observed.load_grants[0] == 0
    assert observed.outputs['io_issueLda_0_ready'] == 0
    assert observed.outputs['io_lduReq_0_bits_meta_valid'] == 1
    assert observed.outputs['io_lduReq_0_bits_meta_entryIdx'] == 3
    assert observed.outputs['io_lduReq_0_bits_meta_elemIdx'] == 19
    assert observed.outputs['io_lduReq_0_bits_req_data_src_0'] == request.vaddr
    assert observed.outputs['io_lduReq_0_bits_req_data_pc'] == request.pc
    assert observed.outputs['io_lduReq_0_bits_req_ctrl_vecWen'] == 1
    assert observed.outputs['io_vagqLsuReq_0_ready'] == 0


def test_std_busy_is_independent_per_lane_and_ready_is_not_valid_dependent():
    observed = observe(Beat(
        vagq_store_data=(
            StoreDataReq(True, 1, 0, 4, 0x1234),
            StoreDataReq(True, 0, 1, 5, 0x5678),
        ),
        std_busy=(True, False),
    ))
    assert observed.outputs['io_vagqStoreDataReq_0_ready'] == 0
    assert observed.outputs['io_vagqStdData_0_valid'] == 0
    assert observed.outputs['io_vagqStoreDataReq_1_ready'] == 1
    assert observed.outputs['io_vagqStdData_1_valid'] == 1
    assert observed.outputs['io_vagqStdData_1_bits_data'] == 0x5678


def test_circular_age_predicates_cover_flag_wrap():
    older = active(0, rob_flag=1, rob_value=1, lq_flag=0, lq_value=1)
    younger = active(1, rob_flag=0, rob_value=0, lq_flag=0, lq_value=2)
    assert _older(older, younger, 0, 1, is_load=True)
